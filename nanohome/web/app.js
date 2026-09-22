/* nanoHome — the page.
   It shows what is on this computer, starts things, opens them, and stops them.
   The only subtlety: starting takes a few seconds, so the page asks how things
   are going instead of waiting. */

const $ = (id) => document.getElementById(id);
const app = {
  state: null,
  timer: null,
  answer: null,      // the app the guide recommended
};

// --------------------------------------------------------------------------
async function get(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || ('The app answered with ' + response.status));
  return data;
}

async function post(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || ('The app answered with ' + response.status));
  return data;
}

function toast(message, kind) {
  const node = document.createElement('div');
  node.className = 'toast' + (kind ? ' ' + kind : '');
  node.textContent = message;
  $('toasts').appendChild(node);
  setTimeout(() => node.remove(), kind === 'bad' ? 11000 : 5000);
}

function busy(button, on, label) {
  if (!button) return;
  if (on) {
    button.dataset.label = button.textContent;
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> ' + (label || 'working…');
  } else {
    button.disabled = false;
    button.textContent = button.dataset.label || label || 'Done';
  }
}

// --------------------------------------------------------------------------
// Loading, and keeping up
// --------------------------------------------------------------------------
async function loadState(checking) {
  busy($('scanBtn'), true, 'looking…');
  try {
    const data = checking ? await post('/api/scan', {}) : await get('/api/state');
    app.state = data;
    render();
    if (data.message) toast(data.message, 'good');
  } catch (error) {
    toast(error.message, 'bad');
  } finally {
    busy($('scanBtn'), false, 'Look again');
    keepUp();
  }
}

/* Poll while anything is starting, and stop polling when everything is settled:
   a page that keeps asking questions when nothing is happening is a page that
   wastes the battery of the laptop it is running on. */
function keepUp() {
  clearTimeout(app.timer);
  const busyNow = (app.state?.apps || []).some((item) =>
    item.state === 'starting' || item.state === 'running' || item.state === 'running-slow');
  app.timer = setTimeout(async () => {
    try {
      const data = await get('/api/state');
      const changed = JSON.stringify(data.apps.map((item) => [item.id, item.state, item.url]))
        !== JSON.stringify((app.state?.apps || []).map((item) => [item.id, item.state, item.url]));
      app.state = data;
      if (changed) render();
      for (const item of data.apps) {
        if (item.state === 'failed' && item.error) {
          const shown = (app.state.shownErrors = app.state.shownErrors || {});
          if (!shown[item.id]) { shown[item.id] = true; toast(item.error, 'bad'); }
        }
      }
    } catch (error) { /* the page keeps working with what it has */ }
    keepUp();
  }, 1500);
}

// --------------------------------------------------------------------------
// Drawing what was found
// --------------------------------------------------------------------------
function render() {
  const state = app.state;
  if (!state) return;
  const found = state.apps.filter((item) => item.found).length;
  $('countPill').textContent = found + ' of ' + state.apps.length + ' apps here';
  $('countPill').className = 'pill ' + (found ? 'good' : 'warn');
  $('headline').textContent = state.sentence;
  $('sentence').textContent = found
    ? 'Press Start on whichever one you need. The first start of an app takes a few seconds; '
      + 'nanoHome waits for it and opens the page for you.'
    : 'Put this nanoHome folder next to the other nano apps, then press “Look again”.';

  const grid = $('appGrid');
  grid.innerHTML = '';
  state.apps.forEach((item) => grid.appendChild(appCard(item)));

  const companions = $('companionList');
  companions.innerHTML = '';
  (state.companions || []).forEach((item) => {
    const row = document.createElement('div');
    row.className = 'sample-item';
    row.innerHTML = '<div class="info"><b></b><span></span></div>';
    row.querySelector('b').textContent = (item.emoji || '') + ' ' + item.name;
    row.querySelector('span').textContent = item.tagline;
    const link = document.createElement('a');
    link.className = 'btn small';
    link.href = item.repo;
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.textContent = 'On GitHub';
    row.appendChild(link);
    companions.appendChild(row);
  });

  renderSearched();
  fillSettings();
}

function stateWord(state) {
  return { starting: 'starting…', running: 'running', 'running-slow': 'starting slowly',
           failed: 'did not start', stopped: 'stopped' }[state] || state;
}

function appCard(item) {
  const card = document.createElement('div');
  card.className = 'app'
    + (item.found ? '' : ' missing')
    + (item.state === 'running' || item.state === 'running-slow' ? ' live' : '');

  const head = document.createElement('div');
  head.className = 'head';
  const dot = document.createElement('span');
  dot.className = 'state-dot ' + (item.state === 'stopped' ? '' : item.state);
  const mark = document.createElement('div');
  mark.className = 'mark';
  mark.textContent = item.emoji;
  const names = document.createElement('div');
  names.className = 'names';
  const name = document.createElement('b');
  name.textContent = item.name;
  const sub = document.createElement('span');
  sub.textContent = item.found ? stateWord(item.state) : 'not on this computer';
  if (item.found && item.state !== 'stopped') sub.textContent += '  ·  port ' + item.port_in_use;
  names.append(name, sub);
  head.append(dot, mark, names);

  const tagline = document.createElement('div');
  tagline.className = 'tagline';
  tagline.textContent = item.tagline;

  const what = document.createElement('div');
  what.className = 'muted';
  what.style.fontSize = '13px';
  what.textContent = item.what;

  card.append(head, tagline, what);

  if (item.found && item.you_can?.length) {
    const list = document.createElement('ul');
    list.className = 'you-can';
    item.you_can.forEach((line) => {
      const bullet = document.createElement('li');
      bullet.textContent = line;
      list.appendChild(bullet);
    });
    card.appendChild(list);
  }

  const actions = document.createElement('div');
  actions.className = 'actions';

  if (!item.found) {
    const hint = document.createElement('div');
    hint.className = 'why';
    hint.textContent = item.missing_pieces?.length
      ? 'Found the folder, but it looks incomplete: ' + item.missing_pieces.join(', ')
      : 'Not found. Add the folder it is in below, or download it from GitHub.';
    card.appendChild(hint);
    const link = document.createElement('a');
    link.className = 'btn small';
    link.href = item.repo;
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.textContent = 'Get it on GitHub';
    actions.appendChild(link);
  } else {
    if (item.state === 'stopped' || item.state === 'failed') {
      const startButton = document.createElement('button');
      startButton.className = 'btn primary';
      startButton.textContent = item.state === 'failed' ? 'Try again' : 'Start';
      startButton.addEventListener('click', () => startApp(item, startButton));
      actions.appendChild(startButton);
    }
    if (item.state === 'running' || item.state === 'running-slow') {
      const openButton = document.createElement('button');
      openButton.className = 'btn primary';
      openButton.textContent = 'Open ' + item.name;
      openButton.addEventListener('click', () => window.open(item.url, '_blank'));
      actions.appendChild(openButton);
      const stopButton = document.createElement('button');
      stopButton.className = 'btn';
      stopButton.textContent = 'Stop';
      stopButton.addEventListener('click', () => stopApp(item, stopButton));
      actions.appendChild(stopButton);
    }
    const logButton = document.createElement('button');
    logButton.className = 'btn ghost small';
    logButton.textContent = 'What it said';
    actions.appendChild(logButton);
    const log = document.createElement('div');
    log.className = 'app-log';
    log.hidden = true;
    logButton.addEventListener('click', async () => {
      log.hidden = !log.hidden;
      if (!log.hidden) {
        try {
          const data = await get('/api/logs/' + item.id);
          log.textContent = data.lines.join('\n') || '(nothing yet)';
        } catch (error) { log.textContent = error.message; }
      }
    });
    const folderButton = document.createElement('button');
    folderButton.className = 'btn ghost small';
    folderButton.textContent = 'Folder';
    folderButton.addEventListener('click', async () => {
      try {
        const data = await post('/api/reveal', { id: item.id });
        toast(data.message, data.opened ? 'good' : 'bad');
      } catch (error) { toast(error.message, 'bad'); }
    });
    actions.appendChild(folderButton);
    card.appendChild(actions);
    card.appendChild(log);
    return card;
  }

  if (item.found) {
    const where = document.createElement('div');
    where.className = 'where';
    where.textContent = item.folder;
    card.appendChild(where);
  }
  card.appendChild(actions);
  return card;
}

async function startApp(item, button) {
  busy(button, true, 'starting…');
  try {
    const answer = await post('/api/start', { id: item.id });
    toast(answer.message || ('Starting ' + item.name + '…'), 'good');
    await loadState();
    // A newly started app is worth opening without being asked twice.
    if (app.state?.settings?.open_browser_when_started) {
      const now = (app.state.apps || []).find((entry) => entry.id === item.id);
      if (now && now.url && now.state === 'running') window.open(now.url, '_blank');
    }
  } catch (error) {
    toast(error.message, 'bad');
  } finally {
    busy(button, false, 'Start');
  }
}

async function stopApp(item, button) {
  busy(button, true, 'stopping…');
  try {
    const answer = await post('/api/stop', { id: item.id });
    toast(answer.message, 'good');
    await loadState();
  } catch (error) {
    toast(error.message, 'bad');
  } finally {
    busy(button, false, 'Stop');
  }
}

function renderSearched() {
  const folders = app.state?.searched || [];
  [$('searchedList'), $('searchedList2')].forEach((holder) => {
    if (!holder) return;
    holder.innerHTML = '';
    folders.forEach((folder) => {
      const row = document.createElement('div');
      row.className = 'sample-item';
      row.innerHTML = '<div class="info"><b></b></div>';
      row.querySelector('b').textContent = folder;
      const remove = document.createElement('button');
      remove.className = 'btn ghost small';
      remove.textContent = '✕';
      remove.title = 'Stop looking here';
      remove.addEventListener('click', async () => {
        const answer = await post('/api/settings', { forget_folder: folder });
        toast(answer.message, 'good');
        loadState();
      });
      row.appendChild(remove);
      holder.appendChild(row);
    });
    if (!folders.length) holder.innerHTML = '<p class="muted">Nothing yet.</p>';
  });
}

// --------------------------------------------------------------------------
// The two questions
// --------------------------------------------------------------------------
function renderQuestions() {
  const holder = $('questions');
  holder.innerHTML = '';
  (app.state?.questions || []).forEach((question) => {
    const field = document.createElement('div');
    field.className = 'field';
    const label = document.createElement('label');
    label.textContent = question.question;
    const select = document.createElement('select');
    select.id = 'q_' + question.name;
    question.options.forEach((option) => {
      const item = document.createElement('option');
      item.value = option.value;
      item.textContent = option.label;
      select.appendChild(item);
    });
    field.append(label, select);
    holder.appendChild(field);
  });
}

async function askGuide() {
  busy($('guideBtn'), true, 'thinking…');
  try {
    const answer = await post('/api/guide', {
      have: $('q_have')?.value, want: $('q_want')?.value,
    });
    app.answer = answer;
    $('answerName').textContent = (answer.emoji || '') + '  ' + answer.name + ' — ' + answer.tagline;
    $('answerWhy').textContent = answer.why;
    $('answerCard').hidden = false;
    $('answerCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (error) {
    toast(error.message, 'bad');
  } finally {
    busy($('guideBtn'), false, 'Which app do I need?');
  }
}

// --------------------------------------------------------------------------
// Settings
// --------------------------------------------------------------------------
function fillSettings() {
  const settings = app.state?.settings || {};
  $('stopOnExit').checked = settings.stop_children_on_exit !== false;
  $('machineInfo').textContent = 'Python ' + (app.state?.python || '?') + '  ·  nanoHome is at '
    + (app.state?.here || '') + '  ·  ' + (app.state?.found_count || 0) + ' of '
    + (app.state?.apps?.length || 0) + ' apps found';
  $('siblingsInfo').textContent = (app.state?.apps || []).map((item) => item.name).join(', ')
    + ' — and the projects with no window: '
    + (app.state?.companions || []).map((item) => item.name).join(', ') + '.';
}

// --------------------------------------------------------------------------
function main() {
  $('scanBtn').addEventListener('click', () => loadState(true));
  $('guideBtn').addEventListener('click', askGuide);
  $('answerCloseBtn').addEventListener('click', () => { $('answerCard').hidden = true; });
  $('answerStartBtn').addEventListener('click', async () => {
    if (!app.answer) return;
    const item = (app.state?.apps || []).find((entry) => entry.id === app.answer.app_id);
    if (!item) return;
    if (!item.found) {
      toast(item.name + ' is not on this computer yet. Add the folder it is in, below.', 'bad');
      return;
    }
    await startApp(item, $('answerStartBtn'));
  });
  $('stopAllBtn').addEventListener('click', async () => {
    try {
      const answer = await post('/api/stop-all', {});
      toast(answer.message, 'good');
      await loadState();
    } catch (error) { toast(error.message, 'bad'); }
  });
  $('addFolderBtn').addEventListener('click', async () => {
    const folder = $('folderInput').value.trim();
    if (!folder) { toast('Type the path of a folder first.', 'bad'); return; }
    try {
      const answer = await post('/api/settings', { add_folder: folder });
      $('folderInput').value = '';
      toast(answer.message, 'good');
      await loadState(true);
    } catch (error) { toast(error.message, 'bad'); }
  });
  $('stopOnExit').addEventListener('change', async () => {
    try {
      await post('/api/settings', { stop_children_on_exit: $('stopOnExit').checked });
      toast('Saved.', 'good');
    } catch (error) { toast(error.message, 'bad'); }
  });
  $('settingsBtn').addEventListener('click', () => $('settingsModal').classList.add('open'));
  document.querySelectorAll('[data-close]').forEach((button) => {
    button.addEventListener('click', () => $(button.dataset.close).classList.remove('open'));
  });
  document.querySelectorAll('.backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop) backdrop.classList.remove('open');
    });
  });
  loadState().then(renderQuestions);
}

main();
