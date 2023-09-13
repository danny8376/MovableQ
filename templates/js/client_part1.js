import { getCookie, setCookie } from "{{ url_for('serve_js', filename='utils.js') }}";

(() => {

  let id0;
  let intervalId = 0;

  const card1 = new bootstrap.Collapse(document.getElementById("card1"), { toggle: false });
  const card2 = new bootstrap.Collapse(document.getElementById("card2"), { toggle: false });
  const card3 = new bootstrap.Collapse(document.getElementById("card3"), { toggle: false });
  const card4 = new bootstrap.Collapse(document.getElementById("card4"), { toggle: false });

  const jobForm = document.getElementById("jobForm");
  const part1Form = document.getElementById("part1Form");

  const part1UploadToggle = document.getElementById("part1UploadToggle");
  const part1UploadFile = document.getElementById("part1_file");
  const part1UploadUrl = document.getElementById("part1_url");

  const miningId0 = document.getElementById("miningId0");
  const miningStatus = document.getElementById("miningStatus");
  const cancelJobButton = document.getElementById("cancelJobButton");

  const movableDownload = document.getElementById("movableDownload");
  const doAnotherButton = document.getElementById("doAnotherButton");

  const canceledModalEl = document.getElementById("canceledModal");
  const canceledModal = new bootstrap.Modal(canceledModalEl);

  const failedModalEl = document.getElementById("failedModal");
  const failedModal = new bootstrap.Modal(failedModalEl);


  // card UI functions

  function showCard1() {
    cancelJobWatch();
    jobForm.reset();
    // update cards
    card1.show();
    card2.hide();
    card3.hide();
    card4.hide();
  }

  function showCard2() {
    part1Form.reset();
    // TODO friend code
    startJobWatch();
    // update cards
    card1.hide();
    card2.show();
    card3.hide();
    card4.hide();
  }

  function showCard3(status) {
    miningId0.innerText = id0;
    switch (status) {
      case "working":
        miningStatus.innerText = "Mining in progress...";
        break;
      case "waiting":
        miningStatus.innerText = "Waiting for an available miner...";
        break;
      default:
        miningStatus.innerText = "Please wait...";
    }
    startJobWatch();
    // update cards
    card1.hide();
    card2.hide();
    card3.show();
    card4.hide();
  }

  function showCard4() {
    cancelJobWatch();
    movableDownload.href = "{{ url_for('download_movable', id0='') }}" + id0;
    // update cards
    card1.hide();
    card2.hide();
    card3.hide();
    card4.show();
  }

  function updateCards(status) {
    switch (status) {
      case "done":
        showCard4();
        break;
      case "waiting":
      case "working":
        showCard3(status);
        break;
      case "need_part1":
        showCard2();
        break;
      case "canceled":
        cancelJobWatch();
        canceledModal.show();
        break;
      case "failed":
        cancelJobWatch();
        failedModal.show();
        break;
      default:
        startOver();
        break;
    }
  }


  // other UI functions

  function togglePart1Upload() {
    if (part1UploadFile.classList.contains("show")) {
      part1UploadUrl.classList.add("show");
      part1UploadFile.classList.remove("show");
      part1UploadToggle.innerText = "Upload a file instead";
    } else {
      part1UploadFile.classList.add("show");
      part1UploadUrl.classList.remove("show");
      part1UploadToggle.innerText = "Provide a URL instead";
    }
  }

  function resetFormFeedback(form) {
    for (let element of form.elements) {
      element.classList.remove("is-invalid");
    }
  }

  function applyJobFormFeedback(feedback) {
    resetFormFeedback(jobForm);
    for (let invalid of feedback.replace("invalid:", "").split(",")) {
      jobForm.elements[invalid].classList.add("is-invalid");
    }
  }

  function applyPart1FormFeedback(feedback) {
    resetFormFeedback(part1Form);
    for (let invalid of feedback.replace("invalid:", "").split(",")) {
      if (invalid == "part1") {
        part1Form.elements["part1_file"].classList.add("is-invalid");
        part1Form.elements["part1_url"].classList.add("is-invalid");
      } else {
        part1Form.elements[invalid].classList.add("is-invalid");
      }
    }
  }


  // actions

  function loadID0() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has("id0")) {
      setID0(urlParams.get("id0"));
    } else {
      setID0(getCookie("id0"));
    }
  }

  function setID0(new_id0) {
    if (new_id0) {
      const urlParams = new URLSearchParams(window.location.search);
      urlParams.set("id0", new_id0);
      window.history.pushState(new_id0, "", window.location.pathname + "?" + urlParams.toString());
    } else {
      // avoid adding duplicate blank history entries
      if (id0) {
        window.history.pushState(new_id0, "", window.location.pathname);
      }
    }
    id0 = new_id0;
    setCookie("id0", id0, 7);
  }

  function startJobWatch() {
    cancelJobWatch();
    intervalId = setInterval(checkJob, 10000);
  }

  function cancelJobWatch() {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = 0;
    }
  }

  function startOver() {
    setID0("");
    cancelJobWatch();
    resetFormFeedback(jobForm);
    resetFormFeedback(part1Form);
    showCard1();
  }

  async function submitJobForm() {
    const formData = new FormData(jobForm);    
    // submit job to server
    let response;
    try {
      response = await fetch("{{ url_for('api_submit_part1_job') }}", {
        method: "POST",
        body: formData
      });
      const responseJson = await response.json();
      if (response.ok) {
        // submission successful
        setID0(responseJson.data.id0);
        checkJob();
      } else {
        // throw error with server message
        throw new Error(responseJson.message);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        // syntax error from parsing non-JSON server error response
        window.alert(`Error submitting job: ${response.status} - ${response.statusText}`);
      } else if (error.message.startsWith("invalid:")) {
        // form input invalid
        applyJobFormFeedback(error.message);
      } else if (error.message === "Duplicate job") {
        // duplicate job
        if (window.confirm("A job with this ID0 already exists. Would you like to view its progress?")) {
          setID0(formData.get("id0"));
          checkJob();
        }
      } else {
        // generic error
        window.alert(`Error submitting job: ${error.message}`);
      }
    }
  }

  async function submitPart1Form() {
    const formData = new FormData(part1Form);    
    // fetch part1 data if selected
    if (part1UploadUrl.classList.contains("show")) {
      try {
        const part1Response = await fetch(part1UploadUrl.value);
        const part1Blob = await part1Response.blob();
        formData.set("part1_file", part1Blob);
      } catch (error) {
        window.alert(`Error downloading part1 data: ${error.message}`);
        return;
      }
    }
    // submit job to server
    let response;
    try {
      response = await fetch("{{ url_for('api_add_part1', id0='') }}" + id0, {
        method: "POST",
        body: formData
      });
      const responseJson = await response.json();
      if (response.ok) {
        // submission successful
        checkJob();
      } else {
        // throw error with server message
        throw new Error(responseJson.message);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        // syntax error from parsing non-JSON server error response
        window.alert(`Error adding part1: ${response.status} - ${response.statusText}`);
      } else if (error.message.startsWith("invalid:")) {
        // form input invalid
        applyPart1FormFeedback(error.message);
      } else {
        // generic error
        window.alert(`Error adding part1: ${error.message}`);
      }
    }
  }

  async function checkJob() {
    if (!id0) {
      showCard1();
      return;
    }
    // grab job status from server
    let response;
    try {
      response = await fetch("{{ url_for('api_check_job_status', id0='') }}" + id0);
      const responseJson = await response.json();
      if (response.ok) {
        updateCards(responseJson.data.status);
        console.log(responseJson);
      } else {
        throw new Error(responseJson.message);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        // syntax error from parsing non-JSON server error response
        window.alert(`Error checking job status: ${response.status} - ${response.statusText}`);
      } else {
        // generic error
        window.alert(`Error checking job status: ${error.message}`);
      }
      startOver();
    }
  }

  async function cancelJob() {
    let response;
    try {
      response = await fetch("{{ url_for('api_cancel_job', id0='') }}" + id0);
      const responseJson = await response.json();
      if (!response.ok) {
        throw new Error(responseJson.message);
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        // syntax error from parsing non-JSON server error response
        window.alert(`Error checking job status: ${response.status} - ${response.statusText}`);
      } else {
        // generic error
        window.alert(`Error checking job status: ${error.message}`);
      }
    }
    startOver();
  }


  document.addEventListener('DOMContentLoaded', () => {
    // event listeners
    cancelJobButton.addEventListener("click", event => cancelJob());
    doAnotherButton.addEventListener("click", event => startOver());
    jobForm.addEventListener("submit", event => {
      event.preventDefault();
      submitJobForm();
    });
    part1Form.addEventListener("submit", event => {
      event.preventDefault();
      submitPart1Form();
    });
    part1UploadToggle.addEventListener("click", event => togglePart1Upload());
    canceledModalEl.addEventListener("hide.bs.modal", event => startOver());
    failedModalEl.addEventListener("hide.bs.modal", event => startOver());

    // initial setup
    togglePart1Upload();
    loadID0();
    checkJob();
  });

})();
