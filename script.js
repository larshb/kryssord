const API = 'https://kryssord.herokuapp.com/search/'


var button = $("button");
var sok = $("#soksynonymer");

function addWildcard() {
  console.log("Adding wildcard...");
  var losning = document.getElementById("losning");
  losning.value = losning.value + "?";
  losning.focus();
}

function sokSynonym() {
  var top_banner = $("top-banner");
  top_banner.addClass("collapse-height");
  document.getElementById("overlay").style.display = "block";

  console.log("Click!")

  var sokeord = document.getElementById("sokeord").value;
  var losning = document.getElementById("losning").value;

  //Clear table
  var table = document.getElementById("output");
  while (table.firstChild) {
    table.removeChild(table.firstChild);
  }

  path = sokeord
  if (losning) {
    path += "/" + losning
  }

  $.ajax({
    url: API + path,
    type: 'GET',
    dataType: 'json',
    success: function(data) {
      document.getElementById("overlay").style.display = "none";
      //console.log(data.data.solutions);
      //var words = data.data.col1;
      //words = words.concat(data.data.col2);
      //console.log(data.data.col2);
      var words = data.results;
      console.log(words);
      bubbleSort(words);
      words.forEach(function(element) {
        console.log(element);

        var txt2 = document.createTextNode(element.length);
        var td2 = document.createElement("td");
        td2.appendChild(txt2);
        td2.style.width = "10px";
        //td2.className = "mdl-data-table__cell--non-numeric";
        //td2.style.width="0%";
        td2.style.margin = 0;

        var tr = document.createElement("tr");
        var td = document.createElement("td");
        var txt = document.createTextNode(element);
        td.appendChild(txt);
        td.className = "mdl-data-table__cell--non-numeric";
        tr.appendChild(td2);
        tr.appendChild(td);
        table.appendChild(tr);
        //return false;
      })
      if (words.length == 0) {
        console.log('lol')
        $('<tr>\
        		<td class="mdl-data-table__cell--non-numeric">\
            Ingen treff :( \
           </td>\
          </tr>').appendTo(table);
      }
    }
  });
}

sok.on("click", function() {
  sokSynonym();
})

function bubbleSort(a) {
  var swapped;
  do {
    swapped = false;
    for (var i = 0; i < a.length - 1; i++) {
      if (a[i].length > a[i + 1].length) {
        var temp = a[i];
        a[i] = a[i + 1];
        a[i + 1] = temp;
        swapped = true;
      }
    }
  } while (swapped);
}
