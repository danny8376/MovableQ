(() => {

  const refreshTablesButton = document.getElementById("refreshTablesButton");

  const jobsTableBody = document.getElementById("jobsTableBody");
  const minersTableBody = document.getElementById("minersTableBody");


  async function refreshTables() {
    refreshJobs();
    refreshMiners();
  }

  async function refreshJobs() {
    const response = await fetch("{{ url_for('api_admin_list_jobs') }}");
    const responseJson = await response.json();
    if (response.ok) {
      if (responseJson.result != "success") {
        window.alert(responseJson.message);
        return;
      }
      updateJobsTable(responseJson.data.jobs);
    } else {
      window.alert("Error retrieving jobs: " + responseJson.message);
    }
  }

  async function refreshMiners() {
    const response = await fetch("{{ url_for('api_admin_list_miners') }}");
    const responseJson = await response.json();
    if (response.ok) {
      if (responseJson.result != "success") {
        window.alert(responseJson.message);
        return;
      }
      updateMinersTable(responseJson.data.miners);
    } else {
      window.alert("Error retrieving miners: " + responseJson.message);
    }
  }


  function updateJobsTable(jobs) {
    jobsTableBody.innerHTML = "";
    for (job of jobs) {
      jobsTableBody.appendChild(createJobRow(job));
    }
  }

  function updateMinersTable(miners) {
    minersTableBody.innerHTML = "";
    for (miner of miners) {
      minersTableBody.appendChild(createMinerRow(miner));
    }
  }

  function createJobRow(job) {
    const row = document.createElement("tr");
    row.className = "align-middle";

    const idCell = document.createElement("td");
    idCell.innerText = job.id0;
    row.appendChild(idCell);

    const statusCell = document.createElement("td");
    statusCell.innerText = job.status;
    row.appendChild(statusCell);

    const createdCell = document.createElement("td");
    const createDate = new Date(job.created);
    createdCell.innerText = createDate.toLocaleString();
    row.appendChild(createdCell);

    const updatedCell = document.createElement("td");
    const updateDate = new Date(job.last_update);
    updatedCell.innerText = updateDate.toLocaleString();
    row.appendChild(updatedCell);

    const assigneeCell = document.createElement("td");
    assigneeCell.innerText = job.assignee;
    row.appendChild(assigneeCell);

    const actionsCell = document.createElement("td");

/*    const requeueButton = document.createElement("button");
    requeueButton.type = "button";
    requeueButton.className = "btn btn-secondary";
    requeueButton.title = "Requeue job";
	const requeueIcon = document.createElement("i");
	requeueIcon.className = "fa-solid fa-arrow-rotate-left";
	requeueButton.appendChild(requeueIcon);
	const requeueText = document.createElement("div");
	requeueText.className = "visually-hidden";
	requeueText.innerText = "Requeue job";
	requeueButton.appendChild(requeueText);
	actionsCell.appendChild(requeueButton);

	actionsCell.appendChild(document.createTextNode(" "));
*/
    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "btn btn-danger";
    if (job.status == "Canceled") {
      cancelButton.classList.add("disabled");
    }
    cancelButton.title = "Cancel job";
    cancelButton.addEventListener("click", event => cancelJob(job.id0));
    const cancelIcon = document.createElement("i");
    cancelIcon.className = "fa-solid fa-xmark";
    cancelButton.appendChild(cancelIcon);
    const cancelText = document.createElement("div");
    cancelText.className = "visually-hidden";
    cancelText.innerText = "Cancel job";
    cancelButton.appendChild(cancelText);
    actionsCell.appendChild(cancelButton);

    row.appendChild(actionsCell);

    return row;
  }

  function createMinerRow(miner) {
    const row = document.createElement("tr");
    row.className = "align-middle";

    const nameCell = document.createElement("td");
    nameCell.innerText = miner.name;
    row.appendChild(nameCell);

    const ipCell = document.createElement("td");
    ipCell.innerText = miner.ip;
    row.appendChild(ipCell);

    const updatedCell = document.createElement("td");
    const updateDate = new Date(miner.last_update);
    updatedCell.innerText = updateDate.toLocaleString();
    row.appendChild(updatedCell);

    return row;
  }


  function requeueJob() {
    // TODO requeue job
  }

  async function cancelJob(id0) {
    const response = await fetch("{{ url_for('api_cancel_job', id0='') }}" + id0);
    const responseJson = await response.json();
    if (response.ok) {
      if (responseJson.result != "success") {
        window.alert(responseJson.message);
        return;
      }
    } else {
      window.alert("Error canceling job: " + responseJson.message);
    }
    refreshJobs();
  }


  document.addEventListener('DOMContentLoaded', () => {
    // event listeners
    refreshTablesButton.addEventListener("click", event => refreshTables());

    // tables refresh
    refreshTables();
    setInterval(refreshTables, 15000);
  });


  // cookie helpers (thank you w3schools)

  function setCookie(cname, cvalue, exdays) {
    const d = new Date();
    d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
    let expires = "expires="+d.toUTCString();
    document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
  }

  function getCookie(cname) {
    let name = cname + "=";
    let ca = document.cookie.split(';');
    for(let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) == ' ') {
        c = c.substring(1);
      }
      if (c.indexOf(name) == 0) {
        return c.substring(name.length, c.length);
      }
    }
    return "";
  }

})();
