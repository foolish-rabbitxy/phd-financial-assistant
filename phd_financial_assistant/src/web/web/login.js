const q = new URLSearchParams(location.search);
if (q.has("error")) document.getElementById("err").classList.remove("hidden");
if (q.has("reset")) document.getElementById("reset-ok").classList.remove("hidden");
