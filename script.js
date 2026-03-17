const API = "https://kryssord.onrender.com/search";

var searchButton = document.querySelector("button");
var synonymSearchInput = document.getElementById("soksynonymer");

function addWildcard(wildcard) {
  console.log("Adding wildcard...");
  var solutionInput = document.getElementById("losning");
  solutionInput.value += wildcard;
  parseTiles();
  solutionInput.focus();
}

function searchSynonyms() {
  // Remove focus from the current element
  document.activeElement.blur();

  // Collapse the top banner and show the overlay
  document.querySelector("#top-banner").classList.add("collapse-height");
  document.getElementById("overlay").style.display = "block";
  // Get the search terms from the input fields
  var searchText = document.getElementById("sokeord").value;
  var solutionText = document.getElementById("losning").value;

  // Clear the output table
  while (document.querySelector("#output tr")) {
    document.querySelector("#output tr").remove();
  }

  // Build the API URL with the search parameters
  const url = new URL(API);
  const params = new URLSearchParams({ a: searchText, b: solutionText });
  url.search = params.toString();

  // Make the API request
  fetch(url)
    .then((response) => response.json())
    .then((data) => {
      // Add the search results to the output table
      data.results.forEach(function (element) {
        var tr = document.createElement("tr");
        tr.innerHTML += `<td class="no-margin word-length-cell">${element.word.length}</td>`;
        tr.innerHTML += `<td class="mdl-data-table__cell--non-numeric">${element.word}</td>`;

        tr.addEventListener("click", function () {
          document.getElementById("sokeord").value = element.word;
          document.getElementById("losning").value = "";
          searchSynonyms();
        });

        tr.style.cursor = "pointer";

        document.querySelector("#output").appendChild(tr);
      });

      // Add the footer to the output table
      var footer =
        data.results.length === 0
          ? " Ingen treff :( "
          : `${data.results.length}`;
      var resultUrl = data.url || "#";

      const newTr = document.createElement("tr");
      const newTd1 = document.createElement("td");
      const newTd2 = document.createElement("td");
      newTd2.classList.add("mdl-data-table__cell--non-numeric");
      newTd2.innerHTML = `<a class="plain" href="${resultUrl}">${footer}</a>`;
      newTr.appendChild(newTd1);
      newTr.appendChild(newTd2);
      newTr.style.cursor = "pointer";
      document.querySelector("#output").appendChild(newTr);

      // Hide the overlay
      document.getElementById("overlay").style.display = "none";
    })
    .catch((error) => {
      console.log(error);
      document.getElementById("overlay").style.display = "none";
    });
}

document.addEventListener("DOMContentLoaded", function () {
  document.querySelector("#show-dialog").addEventListener("click", function () {
    document.getElementById("info").style.display = "block";
  });
  document.querySelectorAll(".close").forEach((element) => {
    element.addEventListener("click", function () {
      document.getElementById("info").style.display = "none";
    });
  });

  // Dummy request to wake up Render service
  const url = new URL(API);
  const params = new URLSearchParams({ a: "nøtt", b: "kr?s*d" });
  url.search = params.toString();
  fetch(url)
    .then((res) => res.json())
    .then(console.log);
});

/* Top overlay illustrative */
const $wildcard = document.createElement("span");
$wildcard.className = "dim";
$wildcard.textContent = "?";
function parseTiles() {
  var txt = document.getElementById("losning").value.toUpperCase();

  // Remove redundant asterisks
  // Asterisks mean any number of characters
  txt = txt.replace(/\*{2,}/g, "*");

  // Preserve cursor position to avoid jumps
  const start = document.getElementById("losning").selectionStart;
  const end = document.getElementById("losning").selectionEnd;
  document.getElementById("losning").value = txt;
  document.getElementById("losning").setSelectionRange(start, end);

  // Remove all cells from tilerow to prevent memory leaks
  while (document.querySelector("#tilerow td")) {
    document.querySelector("#tilerow td").remove();
  }

  // Ensure tileRowElem is a <tr> element before using insertCell()
  if (document.querySelector("#tilerow") && document.querySelector("#tilerow").tagName === "TR") {
    for (const char of txt) {
      let td = document.querySelector("#tilerow").insertCell();

      if (char == "*") td.className = "indef";
      else if (char == "?") $wildcard.cloneNode(true).appendChild(td);
      else td.innerHTML = char;
    }
  } else {
    // Fallback: create td elements and append them manually
    for (const char of txt) {
      let td = document.createElement("td");

      if (char == "*") td.className = "indef";
      else if (char == "?") $wildcard.cloneNode(true).appendChild(td);
      else td.innerHTML = char;

      document.querySelector("#tilerow").appendChild(td);
    }
  }
}

// Putting this into document.addEventListener("DOMContentLoaded", function () breaks its ability to run on updated input for some reason
document.getElementById("losning").addEventListener("input", parseTiles);
