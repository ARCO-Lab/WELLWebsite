/*
 * "Check my CSV format" tool for the Sampling data upload guide (template-sampling-upload.php).
 *
 * It posts the CSV the researcher pasted or chose to the dashboard's /api/samples/validate, which runs the real
 * import validator and returns every problem with its row and column. This file holds NO copy of the format rules:
 * the verdict and the messages come entirely from the dashboard, so the checker can never drift from what the
 * weekly import actually accepts. It also refreshes the reference tables from /api/samples/format, the same
 * canonical lists, as a progressive enhancement over the static tables already in the page.
 *
 * No external libraries; plain DOM APIs.
 */
(function () {
  'use strict';

  var root = document.querySelector('.sampling-checker');
  if (!root) {
    return;
  }

  var VALIDATE_URL = root.getAttribute('data-validate-url');
  var FORMAT_URL = root.getAttribute('data-format-url');
  // Match the backend's own cap (MAX_VALIDATE_BYTES, 2 MB), so an oversize file is caught here with a kind message
  // instead of a bare 413.
  var MAX_BYTES = 2000000;

  var fileInput = document.getElementById('sampling-file');
  var textArea = document.getElementById('sampling-text');
  var checkBtn = document.getElementById('sampling-check-btn');
  var clearBtn = document.getElementById('sampling-clear-btn');
  var result = document.getElementById('sampling-result');

  function esc(text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function byteLength(text) {
    return new Blob([text]).size;
  }

  function show(html, cls) {
    result.className = 'sampling-result ' + (cls || '');
    result.innerHTML = html;
  }

  // Read the CSV text to check: the paste box wins if it has anything, otherwise the chosen file.
  function readInput() {
    return new Promise(function (resolve, reject) {
      var pasted = (textArea.value || '').trim();
      if (pasted) {
        resolve(textArea.value);
        return;
      }
      var file = fileInput.files && fileInput.files[0];
      if (!file) {
        reject(new Error('Paste your CSV, or choose a file, then press Check.'));
        return;
      }
      if (file.size > MAX_BYTES) {
        reject(new Error('That file is larger than 2 MB. A sampling CSV is normally far smaller, so check that you '
          + 'picked the right file.'));
        return;
      }
      var reader = new FileReader();
      reader.onload = function () { resolve(String(reader.result || '')); };
      reader.onerror = function () { reject(new Error('That file could not be read. Try pasting its text instead.')); };
      reader.readAsText(file);
    });
  }

  function renderProblems(problems) {
    var rows = problems.map(function (p) {
      var where = p.row ? ('Row ' + esc(p.row)) : 'Whole file';
      return '<tr><td>' + where + '</td><td>' + esc(p.column || '') + '</td><td>' + esc(p.message) + '</td></tr>';
    }).join('');
    return '<table class="table table-sm sampling-problems"><thead><tr><th>Where</th><th>Column</th>'
      + '<th>What to fix</th></tr></thead><tbody>' + rows + '</tbody></table>';
  }

  function renderResult(data) {
    if (data.ok) {
      var summary = data.summary ? '<p class="mb-0">' + esc(data.summary) + '</p>' : '';
      show('<div class="sampling-result__banner is-ok"><strong>Looks good.</strong> This file matches the format '
        + 'and would import.</div>' + summary, 'is-ok');
      return;
    }
    var problems = data.problems || [];
    var count = problems.length;
    var heading = '<div class="sampling-result__banner is-bad"><strong>Not ready yet.</strong> '
      + esc(count) + (count === 1 ? ' thing' : ' things') + ' to fix. Nothing is imported until every one is '
      + 'resolved.</div>';
    show(heading + renderProblems(problems), 'is-bad');
  }

  function check() {
    show('<p class="mb-0">Checking…</p>', 'is-busy');
    readInput().then(function (text) {
      if (byteLength(text) > MAX_BYTES) {
        show('<div class="sampling-result__banner is-bad">That text is larger than 2 MB, which is more than a '
          + 'sampling CSV should ever be.</div>', 'is-bad');
        return;
      }
      return fetch(VALIDATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ csv: text })
      }).then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok && !Array.isArray(data.problems)) {
            // A transport-level or size error (e.g. 413, 400) that is not the normal "problems" answer.
            throw new Error(data.error || ('The checker could not read that (status ' + res.status + ').'));
          }
          renderResult(data);
        });
      });
    }).catch(function (err) {
      show('<div class="sampling-result__banner is-bad">' + esc(err.message || 'Something went wrong. Please try '
        + 'again, or upload to Borealis and let the weekly import check the file.') + '</div>', 'is-bad');
    });
  }

  checkBtn.addEventListener('click', check);
  clearBtn.addEventListener('click', function () {
    textArea.value = '';
    fileInput.value = '';
    show('', '');
  });

  // Progressive enhancement: replace the static reference tables with the canonical lists from the dashboard, so
  // they always match the validator. On any failure the static tables stay as they are.
  function populateTables() {
    if (!FORMAT_URL) {
      return;
    }
    fetch(FORMAT_URL).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (data) {
      if (!data) {
        return;
      }
      var sites = document.querySelector('#sites-table tbody');
      if (sites && Array.isArray(data.sites)) {
        sites.innerHTML = data.sites.map(function (s) {
          return '<tr><td>' + esc(s.number) + '</td><td>' + esc(s.name) + '</td><td>' + esc(s.creek) + '</td></tr>';
        }).join('');
      }
      var params = document.querySelector('#parameters-table tbody');
      if (params && Array.isArray(data.parameters)) {
        params.innerHTML = data.parameters.map(function (p) {
          var aliases = (p.aliases || []).join(', ');
          return '<tr><td>' + esc(p.name) + '</td><td>' + esc(p.unit) + '</td><td>' + esc(aliases) + '</td></tr>';
        }).join('');
      }
    }).catch(function () { /* keep the static tables */ });
  }

  populateTables();
})();
