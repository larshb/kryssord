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
  // Remove focus from the current element
  document.activeElement.blur();

  // Collapse the top banner and show the overlay
  $("#top-banner").addClass("collapse-height");
  $("#overlay").show();

  // Get the search terms from the input fields
  var sokeordRaw = $("#sokeord").val();
  var losningRaw = $("#losning").val();

  // Clear the output table
  $("#output tr").remove();

  // Build the API URL with the search parameters
  var url = API;
  if (sokeordRaw) {
    url += `?a=${encodeURIComponent(sokeordRaw)}`;
  }
  if (losningRaw) {
    if (url.includes('?')) {
      url += '&';
    } else {
      url += '?';
    }
    url += `b=${encodeURIComponent(losningRaw)}`;
  }

  // Make the API request
  $.ajax({
    url: url,
    type: 'GET',
    dataType: 'json',
    error: function () {
      alert("Ukjent feil. Rar formatering av løsningsord?");
      $("#overlay").hide();
    },
    success: function (data) {
      // Add the search results to the output table
      data.results.forEach(function (element) {
        var tr = $('<tr>')
          .append($('<td class="no-margin word-length-cell">').text(element.word.length))
          .append($('<td class="mdl-data-table__cell--non-numeric">').text(element.word));

        tr.on('click', function () {
          $("#sokeord").val(element.word);
          $("#losning").val("");
          sokSynonym();
        });

        tr.css("cursor", "pointer");

        $("#output").append(tr);
      });

      // Add the footer to the output table
      var footer = data.results.length === 0 ? " Ingen treff :( " : `${data.results.length}`;
      var resultUrl = data.url || "#";
      $('<tr><td></td>' +
        ` <td class="mdl-data-table__cell--non-numeric"> ` +
        `  <a class="plain" href="${resultUrl}">${footer}</a>` +
        ' </td> ' +
        '</tr>').appendTo("#output");

      // Hide the overlay
      $("#overlay").hide();
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
