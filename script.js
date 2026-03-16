const API = 'https://kryssord.onrender.com/search'

var button = $("button");
var sok = $("#soksynonymer");

function addWildcard(wildcard) {
  console.log("Adding wildcard...");
  var losning = document.getElementById("losning");
  losning.value = losning.value + wildcard;
  parseTiles();
  losning.focus();
}

function sokSynonym() {
  document.activeElement.blur();
  var top_banner = $("top-banner"); // Yes, this is a tag, not an id or class. Don't ask.
  top_banner.addClass("collapse-height");
  document.getElementById("overlay").style.display = "block";

  var sokeordRaw = document.getElementById("sokeord").value;
  var losningRaw = document.getElementById("losning").value;

  //Clear table
  var table = document.getElementById("output");
  while (table.firstChild) {
    table.removeChild(table.firstChild);
  }

  var url = API;
  let params = [];
  if (sokeordRaw) {
    params.push(`a=${encodeURIComponent(sokeordRaw)}`);
  }
  if (losningRaw) {
    params.push(`b=${encodeURIComponent(losningRaw)}`);
  }
  if (params.length > 0) {
    url += "?" + params.join("&");
  }
  console.log(url);

  $.ajax({
    url: url,
    type: 'GET',
    dataType: 'json',
    error: function () {
      alert("Ukjent feil. Rar formatering av løsningsord?");
      document.getElementById("overlay").style.display = "none";
    },
    success: function (data) {
      var words = data.results;
      words.forEach(function (element) {

        // Columns: word length, word
        // Header row omitted for brevity

        var txt2 = document.createTextNode(element.word.length);
        var td2 = document.createElement("td");
        td2.appendChild(txt2);
        td2.classList.add("no-margin", "word-length-cell");
        var tr = document.createElement("tr");
        var td = document.createElement("td");
        var txt = document.createTextNode(element.word);
        td.appendChild(txt);
        td.className = "mdl-data-table__cell--non-numeric";
        tr.appendChild(td2);
        tr.appendChild(td);

        /* When the row is clicked, replace 'sokeord' with the word in the row and re-search */
        tr.onclick = function () {
          document.getElementById("sokeord").value = element.word;
          document.getElementById("losning").value = "";
          sokSynonym();
        }

        /* Use pointer cursor to indicate that the row is clickable */
        tr.style.cursor = "pointer";

        table.appendChild(tr);
      })
      let footer;
      if (words.length == 0) {
        footer = " Ingen treff :( ";
      } else {
        footer = `${words.length}`;
        // TODO: Re-implement total number of results reported by kryssord.org
      }
      const resultUrl = data.url ? data.url : "#";
      $('<tr><td></td>' +
        ` <td class="mdl-data-table__cell--non-numeric"> ` +
        `  <a class="plain" href="${resultUrl}">` +
        footer +
        '  </a>' +
        ' </td> ' +
        '</tr>').appendTo(table);
      document.getElementById("overlay").style.display = "none";
    }
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
  $.ajax({
    url: API + '?a=n%C3%B8tt&b=KR%3FS*D',
    type: 'GET',
    dataType: 'json'
  });
})

/* Top overlay illustrative */
const $wildcard = $('<span class="dim">?</span>')
const tin = $("#losning")[0];
const tilerowElem = $("#tilerow")[0];

function parseTiles() {
  var txt = tin.value.toUpperCase();

  // Remove redundant asterisks
  // Asterisks mean any number of characters
  txt = txt.replace(/\*{2,}/g, '*');

  // Preserve cursor position to avoid jumps
  const start = tin.selectionStart;
  const end = tin.selectionEnd;
  tin.value = txt;
  tin.setSelectionRange(start, end);

  // Remove all cells from tilerow to prevent memory leaks
  while (tilerowElem.firstChild) {
    tilerowElem.removeChild(tilerowElem.firstChild);
  }

  // Ensure tilerowElem is a <tr> element before using insertCell()
  if (tilerowElem && tilerowElem.tagName === 'TR') {
    for (const char of txt) {
      let td = tilerowElem.insertCell();

      if (char == '*') td.className = 'indef';
      else if (char == '?') $wildcard.clone().appendTo(td);
      else td.innerHTML = char;
    }
  } else {
    // Fallback: create td elements and append them manually
    for (const char of txt) {
      let td = document.createElement('td');

      if (char == '*') td.className = 'indef';
      else if (char == '?') $wildcard.clone().appendTo(td);
      else td.innerHTML = char;

      tilerowElem.appendChild(td);
    }
  }
}

// Putting this into document.ready breaks its ability to run on updated input for some reason
$("#losning").off('input').on('input', parseTiles);
