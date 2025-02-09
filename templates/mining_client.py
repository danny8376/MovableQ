import base64
import os
import requests
import signal
import struct
import subprocess
import sys
import time
from binascii import hexlify, unhexlify
from urllib.parse import quote as url_quote
from traceback import print_exc


# Do not change! This should be set by the server when downloaded.
client_version = '{{ client_version }}'


# This is the URL of the mining coordination server you would like to use. Be
# sure to replace everything (including the curly braces) if you downloaded
# this script from GitHub.
base_url = '{{ url_for("page_home", _external=True) }}'

# Enter a name for yourself. This name will be associated with your device on
# the mining server and shown on the leaderboard. Any jobs you claim will be
# associated with this name as well, so make sure its appropriate!
miner_name = 'CHANGE_ME'

# Choose which job types you are willing to mine. Note that mii mining jobs
# are typically much more demanding than part1 jobs, and can significantly
# stress your GPU. Part1 jobs are typically shorter, though this does not
# mean you will never claim a demanding/lengthy part1 job!
acceptable_job_types = [ 'part1', 'mii' ]

# set this variable to "True" (without the quotes) if you want to use less of your gpu while mining
# your hash rate will decrease by a bit
force_reduced_work_size = False

# values are in seconds
request_cooldown = 10
error_cooldown = 30
update_interval = 10


# benchmarking options
benchmark_target = 215
benchmark_filename = 'benchmark'
dry_run = False




# Don't edit below this line unless you know what you're doing
lfcs = []
ftune = []
lfcs_new = []
ftune_new = []
err_correct = 0


# from seedminer_launcher3.py by zoogie
# https://github.com/zoogie/seedminer/blob/master/seedminer/seedminer_launcher3.py#L51-L114
def bytes2int(s):
	n = 0
	for i in range(4):
		n += ord(s[i:i + 1]) << (i * 8)
	return n

def int2bytes(n):
	s = bytearray(4)
	for i in range(4):
		s[i] = n & 0xFF
		n = n >> 8
	return s

def byteswap4(n):
	# using a slice to reverse is better, and easier for bytes
	return n[::-1]

def endian4(n):
	return (n & 0xFF000000) >> 24 | (n & 0x00FF0000) >> 8 | (n & 0x0000FF00) << 8 | (n & 0x000000FF) << 24

def getmsed3estimate(n, isnew):
	global err_correct
	newbit = 0x0
	if isnew:
		fc = lfcs_new
		ft = ftune_new
		newbit = 0x80000000
	else:
		fc = lfcs
		ft = ftune

	fc_size = len(fc)
	ft_size = len(ft)

	if fc_size != ft_size:
		return -1

	for i in range(fc_size):
		if n < fc[i]:
			xs = (n - fc[i - 1])
			xl = (fc[i] - fc[i - 1])
			y = ft[i - 1]
			yl = (ft[i] - ft[i - 1])
			ys = ((xs * yl) // xl) + y
			err_correct = ys
			return ((n // 5) - ys) | newbit

	return ((n // 5) - ft[ft_size - 1]) | newbit

# from seedminer_launcher3.py by zoogie
# https://github.com/zoogie/seedminer/blob/master/seedminer/seedminer_launcher3.py#L197-L273
def generate_part2():
	global err_correct

	with open("saves/old-v2.dat", "rb") as f:
		buf = f.read()

	lfcs_len = len(buf) // 8
	err_correct = 0

	for i in range(lfcs_len):
		lfcs.append(struct.unpack("<i", buf[i*8:i*8+4])[0])

	for i in range(lfcs_len):
		ftune.append(struct.unpack("<i", buf[i*8+4:i*8+8])[0])

	with open("saves/new-v2.dat", "rb") as f:
		buf = f.read()

	lfcs_new_len = len(buf) // 8

	for i in range(lfcs_new_len):
		lfcs_new.append(struct.unpack("<i", buf[i*8:i*8+4])[0])

	for i in range(lfcs_new_len):
		ftune_new.append(struct.unpack("<i", buf[i*8+4:i*8+8])[0])

	noobtest = b"\x00" * 0x20
	with open("movable_part1.sed", "rb") as f:
		seed = f.read()
	if noobtest in seed[0x10:0x30]:
		print("Error: ID0 has been left blank, please add an ID0")
		print("Ex: python {} id0 abcdef012345EXAMPLEdef0123456789".format(sys.argv[0]))
		sys.exit(1)
	if noobtest[:4] in seed[:4]:
		print("Error: LFCS has been left blank, did you do a complete two-way friend code exchange before dumping friendlist?")
		sys.exit(1)
	if len(seed) != 0x1000:
		print("Error: movable_part1.sed is not 4KB")
		sys.exit(1)

	if seed[4:5] == b"\x02":
		print("New3DS msed")
		isnew = True
	elif seed[4:5] == b"\x00":
		print("Old3DS msed - this can happen on a New3DS")
		isnew = False
	else:
		print("Error: can't read u8 msed[4]")
		sys.exit(1)

	print("LFCS	  : " + hex(bytes2int(seed[0:4])))
	print("msed3 est : " + hex(getmsed3estimate(bytes2int(seed[0:4]), isnew)))
	print("Error est : " + str(err_correct))
	msed3 = getmsed3estimate(bytes2int(seed[0:4]), isnew)

	offset = 0x10
	hash_final = b""
	i = None
	for i in range(64):
		try:
			hash_init = unhexlify(seed[offset:offset + 0x20])
		except:
			break
		hash_single = byteswap4(hash_init[0:4]) + byteswap4(hash_init[4:8]) + byteswap4(hash_init[8:12]) + byteswap4(hash_init[12:16])
		print("ID0 hash " + str(i) + ": " + hexlify(hash_single).decode('ascii'))
		hash_final += hash_single
		offset += 0x20
	print("Hash total: " + str(i))

	part2 = seed[0:12] + int2bytes(msed3) + hash_final

	pad = 0x1000 - len(part2)
	part2 += b"\x00" * pad

	with open("movable_part2.sed", "wb") as f:
		f.write(part2)
	print("movable_part2.sed generation success")

# from seedminer_launcher3.py by zoogie
# https://github.com/zoogie/seedminer/blob/master/seedminer/seedminer_launcher3.py#L291-L342
def hash_clusterer(id0):
	buf = b""
	hashcount = 0

	try:
		with open("movable_part1.sed", "rb") as f:
			file = f.read()
	except IOError:
		print("movable_part1.sed not found, generating a new one")
		print("don't forget to add an lfcs to it!\n")
		with open("movable_part1.sed", "wb") as f:
			file = b"\x00" * 0x1000
			f.write(file)

	buf += str(id0).encode("ascii")

	print(id0)

	print("Hash added!")

	file = file[:0x10]
	pad_len = 0x1000 - len(file+buf)
	pad = b"\x00" * pad_len
	with open("movable_part1.sed", "wb") as f:
		f.write(file + buf + pad)
	print("There are now {} ID0 hashes in your movable_part1.sed!".format(len(file + buf) // 0x20))
	print("Done!")


def validate_benchmark():
	if os.path.isfile(benchmark_filename):
		return True
	else:
		print('No existing bechmark found!')
		if do_benchmark():
			write_benchmark()
			return True

def write_benchmark():
	with open(benchmark_filename, 'w') as benchmark_file:
		benchmark_file.write(str(benchmark_target))

def erase_benchmark():
	try:
		os.remove(benchmark_filename)
	except:
		pass

def do_benchmark():
	global dry_run
	dry_run = True
	cleanup_mining_files()
	print('Benchmarking...')
	# write impossible part1
	with open('movable_part1.sed', 'wb') as part1_bin:
		content = b'\xFF\xEE\xFF'
		part1_bin.write(content)
		part1_bin.write(b'\0' * (0x1000 - len(content)))
	# run and time bfCL
	try:
		hash_clusterer('fef0fef0fef0fef0fef0fef0fef0fef0')
		generate_part2()
		time_target = time.time() + benchmark_target
		# from seedminer_launcher3.py by zoogie
		# https://github.com/zoogie/seedminer/blob/master/seedminer/seedminer_launcher3.py#L394-L402
		with open("movable_part2.sed", "rb") as f:
			buf = f.read()
		keyy = hexlify(buf[:16]).decode('ascii')
		id0 = hexlify(buf[16:32]).decode('ascii')
		args = "msky {} {} {:08X} {:08X}".format(keyy, id0, endian4(0), endian4(5)).split()
		return_code = run_bfcl('benchmark', args)
		time_finish = time.time()
		if return_code != 101:
			print(f'Finished with an unexpected return code from bfCL: {return_code}')
		elif time_finish > time_target:
			print('Unfortunately, your graphics card is too slow to help mine.')
		else:
			print('Good news, your GPU is fast enough to help mine!')
			return True
	except BfclExecutionError:
		print('There was an error running bfCL! Please figure this out before joining the mining network.')
	finally:
		cleanup_mining_files()
		dry_run = False

def do_mii_mine(model, year, final, timeout=0):
	cleanup_mining_files()

	try:
		# from seedminer_launcher3.py by zoogie
		# https://github.com/zoogie/seedminer/blob/master/seedminer/seedminer_launcher3.py#L140-L184
		start_lfcs = (0x0B000000 if model == "old" else 0x05000000) // 2
		if model == "old":
			model_str = b"\x00\x00"
			if year == 2011:
				start_lfcs = 0x01000000
			elif year == 2012:
				start_lfcs = 0x04000000
			elif year == 2013:
				start_lfcs = 0x07000000
			elif year == 2014:
				start_lfcs = 0x09000000
			elif year == 2015:
				start_lfcs = 0x09800000
			elif year == 2016:
				start_lfcs = 0x0A000000
			elif year == 2017:
				start_lfcs = 0x0A800000
				#start_lfcs = 0x0A650000
		elif model == "new":
			model_str = b"\x02\x00"
			if year == 2014:
				start_lfcs = 0x00800000
			elif year == 2015:
				start_lfcs = 0x01800000
			elif year == 2016:
				start_lfcs = 0x03000000
			elif year == 2017:
				start_lfcs = 0x04000000
		args = "lfcs {:08X} {} {} {:08X}".format(endian4(start_lfcs), hexlify(model_str).decode('ascii'), final, endian4(0))
		print(f'bfcl args:' + args)
		run_bfcl(final, args.split())
		# check output
		if os.path.isfile('movable_part1.sed'):
			print(f'Mining complete! Uploading movable_part1...')
			upload_part1(final)
		else:
			print(f'bfCL was not able to complete the mining job!')
	finally:
		cleanup_mining_files()

def do_part1_mine(id0, part1_data, timeout=0):
	cleanup_mining_files()
	with open('movable_part1.sed', 'wb') as part1_bin:
		part1_bin.write(part1_data)
	try:
		# bfCL
		max_offset = get_max_offset(get_lfcs(part1_data))
		print(f'Using maximum offset: {max_offset}')
		hash_clusterer(id0)
		generate_part2()

		# from seedminer_launcher3.py by zoogie
		# https://github.com/zoogie/seedminer/blob/master/seedminer/seedminer_launcher3.py#L394-L402
		with open("movable_part2.sed", "rb") as f:
			buf = f.read()
		keyy = hexlify(buf[:16]).decode('ascii')
		mid0 = hexlify(buf[16:32]).decode('ascii')
		args = "msky {} {} {:08X} {:08X}".format(keyy, mid0, endian4(0), endian4(max_offset))
		print(f'bfcl args:' + args)
		run_bfcl(id0, args.split())
		# check output
		if os.path.isfile('movable.sed'):
			print(f'Mining complete! Uploading movable...')
			upload_movable(id0)
		else:
			print(f'bfCL was not able to complete the mining job!')
	finally:
		cleanup_mining_files()

def run_bfcl(key, args, rws = force_reduced_work_size):
	try:
		# start mining
		process = subprocess.Popen(['bfcl' if os.name == 'nt' else './bfcl'] + args + (['rws'] if rws else ['sws', 'sm']))
		try:
			timer = 0
			while process.poll() is None:
				timer += 1
				time.sleep(1)
				if timer % update_interval == 0:
					status = update_job(key)
					if status == 'canceled':
						print('Job canceled')
						kill_process(process)
						return
			if not rws and (process.returncode == 251 or process.returncode == 4294967291):  # Help wanted for a better way of catching an exit code of '-5'
				time.sleep(3)  # Just wait a few seconds so we don't burn out our graphics card
				return run_bfcl(key, args, True)
			else:
				check_bfcl_return_code(process.returncode)
		except KeyboardInterrupt:
			kill_process(process)
			print('Terminated bfCL')
			release_job(key)
	except BfclReturnCodeError as e:
		fail_job(key, f'{type(e).__name__}: {e}')
		return e.return_code
	except Exception as e:
		print_exc()
		print('bfCL was not able to run correctly!')
		message = f'{type(e).__name__}: {e}'
		fail_job(key, message)
		raise BfclExecutionError(message) from e

def check_bfcl_return_code(return_code):
	if -1 == return_code:
		raise BfclReturnCodeError(return_code, 'invalid arguments (not verified, could be generic error)')
	elif 101 == return_code:
		raise BfclReturnCodeError(return_code, 'maximum offset reached without a hit')

def get_lfcs(part1_data):
	return int.from_bytes(part1_data[:8], byteorder='little')

# Calculates the max offset bfCL should check for a given LFCS
# Adapted from @eip618's BFM autolauncher script
def get_max_offset(lfcs):
	is_new = lfcs >> 32
	lfcs &= 0xFFFFFFF0
	lfcs |= 0x8

	# determine offsets/distances and load LFCSes for appropriate console type
	if 2 == is_new:
		max_offsets = [	 16,	  16,	  20]
		distances   = [0x00000, 0x00100, 0x00200]
		with open("saves/new-v2.dat", "rb") as lfcs_file:
			lfcs_buffer = lfcs_file.read()
	elif 0 == is_new:
		max_offsets = [	 18,	  18,	  20]
		distances   = [0x00000, 0x00100, 0x00200]
		with open("saves/old-v2.dat", "rb") as lfcs_file:
			lfcs_buffer = lfcs_file.read()
	else:
		raise ValueError('LFCS high u32 is not 0 or 2')

	# unpack LFCSes from binary data
	lfcs_list=[]
	lfcs_count = len(lfcs_buffer) // 8
	for i in range(0, lfcs_count):
		lfcs_list.append(struct.unpack('<I', lfcs_buffer[i*8:i*8+4])[0])

	# compare given LFCS to saved list and find smallest distance estimate
	distance = lfcs - lfcs_list[lfcs_count - 1]
	for i in range(1, lfcs_count - 1):
		if lfcs < lfcs_list[i]:
			distance = min(lfcs - lfcs_list[i-1], lfcs_list[i+1] - lfcs)
			break

	# print('Distance: %08X' % distance)
	# get largest max offset for calulcated distance estimate
	i = 0
	for d in distances:
		if distance < d:
			return max_offsets[i-1] + 10
		i += 1
	return max_offsets[len(distances) - 1] + 10

def cleanup_mining_files():
	lfcs = []
	ftune = []
	lfcs_new = []
	ftune_new = []
	to_remove = ['movable.sed', 'movable_part1.sed']
	for filename in to_remove:
		try:
			os.remove(filename)
		except:
			pass

def request_job():
	if dry_run:
		return
	response = requests.get(f'{base_url}/api/request_job?version={client_version}&name={miner_name}&types={acceptable_job_types}').json()
	result = response['result']
	if 'success' != result:
		error_message = response['message']
		print(f'Error from server: {error_message}')
		return
	return response['data']

def do_job(job):
	job_type = job['type']
	if 'mii' == job_type:
		print('Mii job received:')
		print(f'  Model: {job["model"]}')
		print(f'  Year:  {job["year"]}')
		print(f'  Final: {job["final"]}')
		do_mii_mine(
			job['model'],
			job['year'],
			job['final']
		)
	elif 'part1' == job_type:
		print('Part1 job received:')
		print(f'  ID0:   {job["id0"]}')
		do_part1_mine(
			job['id0'],
			base64.b64decode(job['part1'])
		)
	else:
		print(f'Unknown job type "{job_type}" received, ignoring...')

def update_job(id0):
	if dry_run:
		return
	response = requests.get(f'{base_url}/api/update_job/{id0}')
	return response.json()['data'].get('status')

def release_job(id0):
	if dry_run:
		return
	requests.get(f'{base_url}/api/release_job/{id0}')

def fail_job(id0, note):
	if dry_run:
		return
	requests.post(
		f'{base_url}/api/fail_job/{id0}',
		json={'note': note}
	)

def upload_movable(id0):
	if dry_run:
		return
	with open('movable.sed', 'rb') as movable:
		response = requests.post(
			f'{base_url}/api/complete_job/{id0}',
			json={'result': str(base64.b64encode(movable.read()), 'utf-8')}
		).json()

def upload_part1(final):
	if dry_run:
		return
	with open('movable_part1.sed', 'rb') as movable:
		response = requests.post(
			f'{base_url}/api/complete_job/{final}',
			json={'result': str(base64.b64encode(movable.read()), 'utf-8')}
		).json()

def kill_process(process):
	try:
		if os.name == 'nt':
			process.send_signal(signal.CTRL_C_EVENT)
		else:
			process.send_signal(signal.SIGINT)
		time.sleep(0.25)
	except KeyboardInterrupt:
		pass


class BfclReturnCodeError(Exception):

	def __init__(self, return_code, message):
		self.return_code = return_code
		self.message = message
		super().__init__(f'{return_code}, {message}')


class BfclExecutionError(Exception):

	def __init__(self, message):
		self.message = message
		super().__init__(message)


def run_client():
	global miner_name
	global acceptable_job_types
	# remind miner to change name variable
	if miner_name == 'CHANGE_ME':
		print('Please enter a name first.')
		return
	# sanitize variables
	miner_name = url_quote(miner_name)
	acceptable_job_types = ','.join(acceptable_job_types)
	# benchmark to find issues before claiming real jobs
	if not validate_benchmark():
		return
	# main mining loop
	while True:
		try:
			try:
				job = request_job()
				if job:
					print() # wait message carriage return fix
					do_job(job)
				else:
					print(f'No mining jobs, waiting {request_cooldown} seconds...', end='\r')
				time.sleep(request_cooldown)
			finally:
				print() # wait message carriage return fix
		except KeyboardInterrupt:
			should_exit = input('Would you like to exit? (y/n): ')
			if should_exit.lower().startswith('y'):
				break
		except BfclExecutionError as e:
			# errors not arising from return codes mean a bigger issue
			erase_benchmark()
			break
		except:
			print_exc()
			print(f'Error contacting mining site, waiting {error_cooldown} seconds...')
			time.sleep(error_cooldown)

if __name__ == '__main__':
	run_client()
