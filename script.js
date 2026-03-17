const API = "https://kryssord.onrender.com/search";

var searchButton = $("button");
var synonymSearchInput = $("#soksynonymer");

function addWildcard(wildcard) {
  console.log("Adding wildcard...");
  var solutionInput = document.getElementById("losning");
  solutionInput.value = solutionInput.value + wildcard;
  parseTiles();
  solutionInput.focus();
}

function searchSynonyms() {
  // Remove focus from the current element
  document.activeElement.blur();

  // Collapse the top banner and show the overlay
  $("#top-banner").addClass("collapse-height");
  $("#overlay").show();

  // Get the search terms from the input fields
  var searchText = $("#sokeord").val();
  var solutionText = $("#losning").val();

  // Clear the output table
  $("#output tr").remove();

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
        var tr = $("<tr>")
          .append(
            $('<td class="no-margin word-length-cell">').text(
              element.word.length,
            ),
          )
          .append(
            $('<td class="mdl-data-table__cell--non-numeric">').text(
              element.word,
            ),
          );

        tr.on("click", function () {
          $("#sokeord").val(element.word);
          $("#losning").val("");
          searchSynonyms();
        });

        tr.css("cursor", "pointer");

        $("#output").append(tr);
      });

      // Add the footer to the output table
      var footer =
        data.results.length === 0
          ? " Ingen treff :( "
          : `${data.results.length}`;
      var resultUrl = data.url || "#";
      $(
        "<tr><td></td>" +
          ` <td class="mdl-data-table__cell--non-numeric"> ` +
          `  <a class="plain" href="${resultUrl}">${footer}</a>` +
          " </td> " +
          "</tr>",
      ).appendTo("#output");

      // Hide the overlay
      $("#overlay").hide();
    })
    .catch((error) => {
      alert("Ukjent feil. Rar formatering av løsningsord?");
      $("#overlay").hide();
    });
}

$(document).ready(function () {
  $("#show-dialog").click(function () {
    $("#info").fadeIn();
  });
  $(".close").click(function () {
    $("#info").fadeOut();
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
const $wildcard = $('<span class="dim">?</span>');
const solutionInputElem = $("#losning")[0];
const tileRowElem = $("#tilerow")[0];

function parseTiles() {
  var txt = solutionInputElem.value.toUpperCase();

  // Remove redundant asterisks
  // Asterisks mean any number of characters
  txt = txt.replace(/\*{2,}/g, "*");

  // Preserve cursor position to avoid jumps
  const start = solutionInputElem.selectionStart;
  const end = solutionInputElem.selectionEnd;
  solutionInputElem.value = txt;
  solutionInputElem.setSelectionRange(start, end);

  // Remove all cells from tilerow to prevent memory leaks
  while (tileRowElem.firstChild) {
    tileRowElem.removeChild(tileRowElem.firstChild);
  }

  // Ensure tileRowElem is a <tr> element before using insertCell()
  if (tileRowElem && tileRowElem.tagName === "TR") {
    for (const char of txt) {
      let td = tileRowElem.insertCell();

      if (char == "*") td.className = "indef";
      else if (char == "?") $wildcard.clone().appendTo(td);
      else td.innerHTML = char;
    }
  } else {
    // Fallback: create td elements and append them manually
    for (const char of txt) {
      let td = document.createElement("td");

      if (char == "*") td.className = "indef";
      else if (char == "?") $wildcard.clone().appendTo(td);
      else td.innerHTML = char;

      tileRowElem.appendChild(td);
    }
  }
}

// Putting this into document.ready breaks its ability to run on updated input for some reason
$("#losning").off("input").on("input", parseTiles);
