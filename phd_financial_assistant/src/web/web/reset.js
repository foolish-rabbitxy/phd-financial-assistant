// Shared by forgot.html and reset.html.
const q = new URLSearchParams(location.search);
const sent = document.getElementById("sent");
if (sent && q.has("sent")) sent.classList.remove("hidden");
const token = document.getElementById("token");
if (token) token.value = q.get("token") || "";
const err = document.getElementById("err");
if (err && q.get("error")) { err.textContent = q.get("error"); err.classList.remove("hidden"); }
