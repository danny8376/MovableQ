from transitions import Machine

from collections import deque
from datetime import datetime, timedelta, timezone
import json
import os
from threading import RLock
import base64


mii_part1_path = os.getenv('MIIP1S_PATH', './miip1s')
movable_path = os.getenv('MSEDS_PATH', './mseds')
job_lifetime = timedelta(minutes=5)
miner_lifetime = timedelta(minutes=10)


class JobManager():

    def __init__(self):
        self.jobs = {}
        self.wait_queue = deque()
        self.miners = {}
        self.lock = RLock()

    # adds a job to the current job list, raises a ValueError if it exists already
    def submit_job(self, job):
        with self.lock:
            if self.job_exists(job.key):
                raise ValueError(f'Duplicate job: {job.key}')
            self.jobs[job.key] = job

    # adds a part1 file to a job
    def add_part1(self, id0, part1):
        with self.lock:
            self.jobs[id0].add_part1(part1)

    # set job status to canceled, KeyError if it does not exist
    def cancel_job(self, key):
        with self.lock:
            job = self.jobs[key]
            job.to_canceled()
            self._unqueue_job(key)

    # reset a canceled job
    def reset_job(self, key):
        with self.lock:
            job = self.jobs[key]
            job.reset()
            job.prepare()
            if 'ready' == job.state:
                self.queue_job(key)

    # delete job from the current job list if exists
    def delete_job(self, key):
        with self.lock:
            del self.jobs[key]
            self._unqueue_job(key)

    # add job id to queue
    def _queue_job(self, key, urgent=False):
        if urgent:
            self.wait_queue.appendleft(key)
        else:
            self.wait_queue.append(key)

    # add job id to queue, raises ValueError if it was already queued
    def queue_job(self, key, urgent=False):
        with self.lock:
            job = self.jobs[key]
            job.queue()
            self._queue_job(key, urgent)

    # removes an id0 from the job queue if it was queued before
    def _unqueue_job(self, key):
        if key in self.wait_queue:
            self.wait_queue.remove(key)

    # removes an id0 from the job queue, raises ValueError if it was not queued
    def unqueue_job(self, key):
        with self.lock:
            job = self.jobs[key]
            job.unqueue()
            self._unqueue_job(job.key)

    # pop from job queue, optionally filtering by type
    def _get_job(self, accepted_types=None):
        if len(self.wait_queue) == 0:
            return
        if accepted_types:
            for key in self.wait_queue:
                job = self.jobs[key]
                if job.type in accepted_types:
                    self.wait_queue.remove(key)
                    return job
        else:
            return self.jobs[self.wait_queue.popleft()]

    # pop from job queue if not empty and assign, optionally filtering by type
    def request_job(self, miner_name=None, miner_ip=None, accepted_types=None):
        with self.lock:
            miner = self.update_miner(miner_name, miner_ip)
            job = self._get_job(accepted_types)
            if job:
                job.assign(miner)
                return job

    # set job status to canceled, KeyError if it does not exist
    def release_job(self, key):
        with self.lock:
            job = self.jobs[key]
            job.release()
            self._queue_job(key, urgent=True)

    # returns False if a job was canceled, updates its time/miner and returns True otherwise
    def update_job(self, key, miner_ip=None):
        with self.lock:
            job = self.jobs[key]
            if 'canceled' == job.state:
                return False
            job.update()
            if job.assignee:
                self.update_miner(job.assignee.name, miner_ip)
            return True

    # if a name is provided, updates that miners ip and time, creating one if necessary; returns the Miner object
    def update_miner(self, name, ip=None):
        with self.lock:
            if name:
                if name in self.miners:
                    self.miners[name].update(ip)
                else:
                    self.miners[name] = Miner(name, ip)
                return self.miners[name]

    # save movable to disk and delete job
    def complete_job(self, key, result):
        with self.lock:
            job = self.jobs[key]
            job.complete()
            if job.type == 'mii':
                save_mii_part1(key, result)
            elif job.type == 'part1':
                save_movable(key, result)
            self.fulfill_job(key, result)
            self.delete_job(key)

    # fulfill jobs that have prerequisite
    def fulfill_job(self, key, part1=None):
        if not part1:
            part1 = read_mii_part1(key)
        part1 = str(base64.b64encode(part1), 'utf-8')
        with self.lock:
            for job in self.jobs.values():
                if job.type == 'part1' and job.prerequisite == key:
                    job.add_part1(part1)
                    self.queue_job(job.key)

    # mark job as failed and attach note
    def fail_job(self, key, note=None):
        with self.lock:
            job = self.jobs[key]
            job.fail(note)

    # requeue dead jobs
    def release_dead_jobs(self):
        with self.lock:
            released = []
            for job in self.jobs.values():
                if 'working' == job.state and job.has_timed_out():
                    job.release()
                    released.append(job.key)
            for key in released:
                self._queue_job(key, urgent=True)
            return released

    # delete old canceled jobs
    def trim_canceled_jobs(self):
        with self.lock:
            deleted = []
            for job in self.jobs.values():
                if 'canceled' == job.state and job.has_timed_out():
                    deleted.append(job.key)
            for key in deleted:
                self.delete_job(key)
            return deleted

    # True if current job exists
    def job_exists(self, key):
        with self.lock:
            return key in self.jobs

    # return job status if found, finished if movable exists, KeyError if neither
    def check_job_status(self, key, extra_info=False):
        with self.lock:
            try:
                job = self.jobs[key]
                return job.state
            except KeyError as e:
                if len(key) == 16 and mii_part1_exists(key):
                    return 'done'
                elif len(key) == 32 and movable_exists(key):
                    return 'done'
                else:
                    raise e

    def get_mining_stats(self, key):
        with self.lock:
            job = self.jobs[key]
            return {
                'assignee': job.get_assignee_name(),
                'rate': job.mining_rate,
                'offset': job.mining_offset
            }

    # returns all current jobs, optionally only those with a specific status
    def list_jobs(self, status_filter=None):
        with self.lock:
            if status_filter:
                return [j for j in self.jobs.values() if j.state == status_filter]
            else:
                return self.jobs.values()

    # returns the number of current jobs, optionally only counting those with a specific status
    def count_jobs(self, status_filter=None):
        return len(self.list_jobs(status_filter))

    # returns a list of all miners, or optionally only the active ones
    def list_miners(self, active_only=False):
        with self.lock:
            if active_only:
                return [m for m in self.miners.values() if not m.has_timed_out()]
            else:
                return self.miners.values()

    # returns the number of miners, optionally only counting the active ones
    def count_miners(self, active_only=False):
        return len(self.list_miners(active_only))


class Job(Machine):

    # states
    states = [
        'submitted',
        'ready',
        'waiting',
        'working',
        'canceled',
        'failed',
        'done'
    ]

    transitions = [
        {
            'trigger': 'queue',
            'source': 'ready',
            'dest': 'waiting'
        },
        {
            'trigger': 'unqueue',
            'source': 'waiting',
            'dest': 'ready'
        },
        {
            'trigger': 'assign',
            'source': 'waiting',
            'dest': 'working',
            'before': 'on_assign'
        },
        {
            'trigger': 'release',
            'source': 'working',
            'dest': 'waiting'
        },
        {
            'trigger': 'reset',
            'source': 'canceled',
            'dest': 'submitted'
        },
        {
            'trigger': 'fail',
            'source': 'working',
            'dest': 'failed',
            'before': 'on_fail'
        },
        {
            'trigger': 'complete',
            'source': 'working',
            'dest': 'done'
        }
    ]

    # note that _type is used instead of just type (avoids keyword collision)
    def __init__(self, key, _type):
        super().__init__(
            states=Job.states,
            transitions=Job.transitions,
            initial='submitted'
        )
        # job properties
        self.key = key
        self.type = _type
        self.note = None
        # for queue
        self.created = datetime.now(tz=timezone.utc)
        self.assignee = None
        self.last_update = self.created
        # mining stats
        self.mining_rate = None
        self.mining_offset = None

    def update(self):
        self.last_update = datetime.now(tz=timezone.utc)

    def on_assign(self, miner):
        self.assignee = miner
        self.update()

    def on_fail(self, note=None):
        self.note = note

    def get_assignee_name(self):
        return self.assignee.name if self.assignee else None

    # True if the job has timed out, False if it has not
    def has_timed_out(self):
        return datetime.now(tz=timezone.utc) > (self.last_update + job_lifetime)

    def __iter__(self):
        # job properties
        yield 'key', self.key
        yield 'type', self.type
        yield 'status', self.state
        yield 'note', self.note
        # for queue
        yield 'created', self.created.isoformat()
        yield 'assignee', self.get_assignee_name()
        yield 'last_update', self.last_update.isoformat()
        # mining stats
        yield 'mining_rate', self.mining_rate
        yield 'mining_offset', self.mining_offset


class MiiJob(Job):

    def __init__(self, id0, model, year, final):
        super().__init__(id0, 'mii')
        self.add_transition('prepare', 'submitted', 'ready')
        # mii-specific job properties
        self.console_model = model
        self.console_year = year
        # mii jobs are ready immediately
        self.prepare()

    def __iter__(self):
        yield from super().__iter__()
        yield 'model', self.console_model
        yield 'year', self.console_year
        yield 'final', self.key


class FCJob(Job):

    def __init__(self, friend_code=None):
        super().__init__(friend_code, 'fc')
        self.add_transition('prepare', 'submitted', 'ready')
        # part1-specific job properties
        self.friend_code = friend_code
        # part1 jobs need part1 (duh)
        self.prepare()

    def __iter__(self):
        yield from super().__iter__()
        yield 'friend_code', self.key


class Part1Job(Job):

    def __init__(self, id0, part1=None, prerequisite=None):
        super().__init__(id0, 'part1')
        self.add_state('need_part1')
        self.add_transition('prepare', 'submitted', 'need_part1', after='on_prepare')
        self.add_transition('add_part1', 'need_part1', 'ready', before='on_add_part1')
        # part1-specific job properties
        self.part1 = part1
        self.prerequisite = prerequisite
        # part1 jobs need part1 (duh)
        self.prepare(part1)

    def on_prepare(self, part1=None):
        if part1:
            self.add_part1(part1)
        elif self.part1:
            self.to_ready()
    
    def on_add_part1(self, part1):
        self.part1 = part1

    def has_part1(self):
        if self.part1:
            return True
        else:
            return False

    def __iter__(self):
        yield from super().__iter__()
        yield 'id0', self.key
        yield 'part1', self.part1
        yield 'prerequisite', self.prerequisite


class Miner():

    def __init__(self, name, ip=None):
        self.name = name
        self.ip = ip
        self.update()

    def update(self, ip=None):
        self.last_update = datetime.now(tz=timezone.utc)
        if ip:
            self.ip = ip

    # True if the miner has timed out, False if they have not
    def has_timed_out(self):
        return datetime.now(tz=timezone.utc) > (self.last_update + miner_lifetime)

    def __iter__(self):
        yield 'name', self.name
        yield 'ip', self.ip
        yield 'last_update', self.last_update.isoformat()


def mii_final_to_part1_path(final, create=False):
    dir = os.path.join(mii_part1_path, f'{final[0:2]}/{final[2:4]}')
    if create:
        os.makedirs(dir, exist_ok=True)
    return os.path.join(dir, final)

def mii_part1_exists(final):
    part1_path = mii_final_to_part1_path(final)
    return os.path.isfile(part1_path)

def save_mii_part1(final, part1):
    with open(mii_final_to_part1_path(final, create=True), 'wb') as part1_file:
        part1_file.write(part1)

def read_mii_part1(final):
    if not mii_part1_exists(final):
        return
    with open(mii_final_to_part1_path(final), 'rb') as part1_file:
        return part1_file.read()


def id0_to_movable_path(id0, create=False):
    dir = os.path.join(movable_path, f'{id0[0:2]}/{id0[2:4]}')
    if create:
        os.makedirs(dir, exist_ok=True)
    return os.path.join(dir, id0)

def movable_exists(id0):
    movable_path = id0_to_movable_path(id0)
    return os.path.isfile(movable_path)

def save_movable(id0, movable):
    with open(id0_to_movable_path(id0, create=True), 'wb') as movable_file:
        movable_file.write(movable)

def read_movable(id0):
    if not movable_exists(id0):
        return
    with open(id0_to_movable_path(id0), 'rb') as movable_file:
        return movable_file.read()


def count_total_mined():
    return sum(len(files) for _, _, files in os.walk(movable_path))
