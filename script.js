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
  var top_banner = $("top-banner");
  top_banner.addClass("collapse-height");
  document.getElementById("overlay").style.display = "block";

  var sokeord = document.getElementById("sokeord").value.replace(/\?/g, '%3F');
  var losning = document.getElementById("losning").value.replace(/\?/g, '%3F');

  //Clear table
  var table = document.getElementById("output");
  while (table.firstChild) {
    table.removeChild(table.firstChild);
  }

  // Legacy:
  // path = sokeord
  // if (losning) {
  //   path += "/" + losning
  // }
  // var url = API + path;
  // console.log(url);

  // New API where sokeord is put into key 'a' and the optional losning is put into key 'b'
  var url = `${API}?a=${sokeord}`;
  if (losning) {
    url += `&b=${losning}`;
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

        var txt2 = document.createTextNode(element.word.length);
        var td2 = document.createElement("td");
        td2.appendChild(txt2);
        td2.style.width = "10px";
        td2.style.margin = 0;

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
      if (words.length == 0) {
        footer = " Ingen treff :( ";
      } else {
        footer = `${words.length}`; /*/${data.nresults}`;*/
        /* TODO: Re-implement total number of results */
      }
      $('<tr><td></td>' +
        ' <td href="#" class="mdl-data-table__cell--non-numeric"> ' +
        `  <a class="plain" href="${data.url}">` +
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
const tr = $("#tilerow")[0];

function parseTiles() {
  var txt = tin.value.toUpperCase();

  /* Deferr unnecessary wildcards */
  txt = txt.replace('**', '*');
  tin.value = txt;

  $("#tilerow").empty();
  for (const char of txt) {
    td = tr.insertCell();

    if (char == '*') td.className = 'indef';
    else if (char == '?') $wildcard.clone().appendTo(td);
    else td.innerHTML = char;
  }
}

$("#losning").on('input', parseTiles);
