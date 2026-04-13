const express = require('express');
const router = express.Router();
const { spawn } = require('child_process');
const path = require('path');
const dotenv = require('dotenv');

const STORYBOARD_BACKEND = path.join(__dirname, '..', '..', 'storyboard-backend');
const MAIN_SCRIPT = path.join(STORYBOARD_BACKEND, 'main.py');

function runPipeline(input) {
  return new Promise((resolve, reject) => {
    dotenv.config({ path: path.join(STORYBOARD_BACKEND, '.env') });
    const proc = spawn('python', [MAIN_SCRIPT], {
      cwd: STORYBOARD_BACKEND,
      env: process.env,
    });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('error', (err) => reject(new Error('Python not found or main.py failed: ' + err.message)));
    proc.on('close', (code) => {
      try {
        const data = JSON.parse(stdout || '{}');
        if (data.error) {
          reject(new Error(data.error));
          return;
        }
        if (code !== 0) {
          reject(new Error(stderr || data.error || 'Pipeline failed'));
          return;
        }
        resolve(data);
      } catch (e) {
        reject(new Error(stderr || 'Invalid Python output'));
      }
    });
    proc.stdin.write(JSON.stringify(input));
    proc.stdin.end();
  });
}

// POST /api/storyboard/extract-script — scriptText or pdfBase64 → { scriptText }
router.post('/extract-script', async (req, res) => {
  try {
    const { scriptText, pdfBase64 } = req.body || {};
    const result = await runPipeline({
      action: 'extract_script',
      scriptText: scriptText || '',
      pdfBase64: pdfBase64 || null,
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] extract-script:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Extract failed' });
  }
});

// POST /api/storyboard/characters — scriptText, style → { characters: [{ name, imageBase64 }] }
router.post('/characters', async (req, res) => {
  try {
    const { scriptText, style } = req.body || {};
    const result = await runPipeline({
      action: 'get_characters',
      scriptText: scriptText || '',
      style: style || 'realistic',
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] characters:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Character generation failed' });
  }
});

// POST /api/storyboard/regenerate-character — characterName, userFeedback, scriptText, characterDescription?, style
router.post('/regenerate-character', async (req, res) => {
  try {
    const { characterName, userFeedback, scriptText, characterDescription, style } = req.body || {};
    const result = await runPipeline({
      action: 'regenerate_character',
      characterName: characterName || '',
      userFeedback: userFeedback || '',
      scriptText: scriptText || '',
      characterDescription: characterDescription || '',
      style: style || 'realistic',
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] regenerate-character:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Regenerate failed' });
  }
});

// POST /api/storyboard/props — scriptText, style → { props: [{ name, imageBase64 }] }
router.post('/props', async (req, res) => {
  try {
    const { scriptText, style } = req.body || {};
    const result = await runPipeline({
      action: 'get_props',
      scriptText: scriptText || '',
      style: style || 'realistic',
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] props:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Props generation failed' });
  }
});

// POST /api/storyboard/regenerate-prop — propName, userFeedback, scriptText, propDescription?, style
router.post('/regenerate-prop', async (req, res) => {
  try {
    const { propName, userFeedback, scriptText, propDescription, style } = req.body || {};
    const result = await runPipeline({
      action: 'regenerate_prop',
      propName: propName || '',
      userFeedback: userFeedback || '',
      scriptText: scriptText || '',
      propDescription: propDescription || '',
      style: style || 'realistic',
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] regenerate-prop:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Regenerate failed' });
  }
});

// POST /api/storyboard/environments/identify — scriptText → { environments: [labels] }
router.post('/environments/identify', async (req, res) => {
  try {
    const { scriptText } = req.body || {};
    const result = await runPipeline({ action: 'identify_environments', scriptText: scriptText || '' });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] environments/identify:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Identify failed' });
  }
});

// POST /api/storyboard/environments/get — scriptText, style, userEnvironments? → { environments: [{ name, imageBase64 }] }
router.post('/environments/get', async (req, res) => {
  try {
    const { scriptText, style, userEnvironments } = req.body || {};
    const result = await runPipeline({
      action: 'get_environments',
      scriptText: scriptText || '',
      style: style || 'realistic',
      userEnvironments: Array.isArray(userEnvironments) ? userEnvironments : [],
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] environments/get:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Environments get failed' });
  }
});

// POST /api/storyboard/environments/regenerate — environmentName, userFeedback?, style?, referenceEnvironments?
router.post('/environments/regenerate', async (req, res) => {
  try {
    const { environmentName, userFeedback, style, referenceEnvironments } = req.body || {};
    const result = await runPipeline({
      action: 'regenerate_environment',
      environmentName: environmentName || '',
      userFeedback: userFeedback || '',
      style: style || 'realistic',
      referenceEnvironments: Array.isArray(referenceEnvironments) ? referenceEnvironments : [],
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] environments/regenerate:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Regenerate failed' });
  }
});

// POST /api/storyboard/approve — save characters, props, and environments to JSON
router.post('/approve', async (req, res) => {
  try {
    const { characters, props, environments } = req.body || {};
    await runPipeline({
      action: 'approve',
      characters: characters || [],
      props: props || [],
      environments: environments || [],
    });
    res.json({ ok: true });
  } catch (err) {
    console.error('[StoryBoard] approve:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Save failed' });
  }
});

// POST /api/storyboard/scenes — scriptText, style, aspectRatio → { scenes: [{ sceneIndex, title, imageBase64 }] }
router.post('/scenes', async (req, res) => {
  try {
    const { scriptText, style, aspectRatio } = req.body || {};
    const result = await runPipeline({
      action: 'generate_scenes',
      scriptText: scriptText || '',
      style: style || 'realistic',
      aspectRatio: aspectRatio || '16:9',
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] scenes:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Scene generation failed' });
  }
});

// POST /api/storyboard/reset — clear characters.json (call on page load/refresh)
router.post('/reset', async (req, res) => {
  try {
    await runPipeline({ action: 'reset' });
    res.json({ ok: true });
  } catch (err) {
    console.error('[StoryBoard] reset:', err?.message || err);
    res.status(500).json({ error: err?.message || 'Reset failed' });
  }
});

// POST /api/storyboard/history/save — save one storyboard run (scenes) under a name
router.post('/history/save', async (req, res) => {
  try {
    const { storyboardName, scenes } = req.body || {};
    const result = await runPipeline({
      action: 'save_history',
      storyboardName: storyboardName || '',
      scenes: Array.isArray(scenes) ? scenes : [],
    });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] history/save:', err?.message || err);
    res.status(500).json({ error: err?.message || 'History save failed' });
  }
});

// GET /api/storyboard/history — list all saved storyboard runs with their scenes
router.get('/history', async (_req, res) => {
  try {
    const result = await runPipeline({ action: 'get_history' });
    res.json(result);
  } catch (err) {
    console.error('[StoryBoard] history:', err?.message || err);
    res.status(500).json({ error: err?.message || 'History fetch failed' });
  }
});

module.exports = router;
