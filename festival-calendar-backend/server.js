require('dotenv').config();

const path = require('path');
const express = require('express');
const cors = require('cors');

// Global guard: don't crash the process on transient socket write errors (EOF/ECONNRESET/EPIPE)
process.on('uncaughtException', (err) => {
  if (err && (err.code === 'EOF' || err.code === 'ECONNRESET' || err.code === 'EPIPE')) {
    console.warn('[Server] Ignored uncaught transient error:', err.code);
    return;
  }
  console.error('[Server] Uncaught exception:', err);
});

process.on('unhandledRejection', (reason) => {
  const err = reason instanceof Error ? reason : undefined;
  if (err && (err.code === 'EOF' || err.code === 'ECONNRESET' || err.code === 'EPIPE')) {
    console.warn('[Server] Ignored unhandled rejection with transient error:', err.code);
    return;
  }
  console.error('[Server] Unhandled rejection:', reason);
});

function loadRouteOrNull(routePath) {
  try {
    return require(routePath);
  } catch (err) {
    console.warn(`[Server] Skipping missing route module: ${routePath}`);
    return null;
  }
}

const generateRoute = loadRouteOrNull('./routes/generate');
const multiposterRoute = loadRouteOrNull('./routes/multiposter');
const manthanRoute = loadRouteOrNull('./routes/manthan');
const storyboardRoute = loadRouteOrNull('./routes/storyboard');
const festivalCalendarHistoryRoute = loadRouteOrNull('./routes/festivalCalendarHistory');
const rembrandtRoute = loadRouteOrNull('./routes/rembrandt');

const PORT = process.env.PORT || 5600;
const WEBSITE_ROOT = path.join(__dirname, '..');

const app = express();

app.use(express.json({ limit: '200mb' }));
app.use(express.urlencoded({ limit: '200mb', extended: true }));

app.use(cors({ origin: true, credentials: true }));

// Log API requests for debugging
app.use('/api/', (req, res, next) => {
  if (req.method === 'POST') {
    console.log(`[API] ${req.method} ${req.path}`);
  }
  next();
});

if (generateRoute) app.use('/api/festival-calendar/generate', generateRoute);
if (festivalCalendarHistoryRoute) app.use('/api/festival-calendar', festivalCalendarHistoryRoute);
if (multiposterRoute) app.use('/api/multiposter', multiposterRoute);
if (manthanRoute) app.use('/api/manthan', manthanRoute);
if (storyboardRoute) app.use('/api/storyboard', storyboardRoute);
if (rembrandtRoute) app.use('/api/rembrandt', rembrandtRoute);

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.get('/', (req, res) => {
  res.sendFile(path.join(WEBSITE_ROOT, 'StoryBoard.html'));
});

app.use(express.static(WEBSITE_ROOT));

app.use((err, req, res, next) => {
  if (err.code === 'LIMIT_FILE_SIZE' || err.type === 'entity.too.large') {
    return res.status(413).json({ error: 'Request body too large. Try fewer or smaller images.' });
  }
  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Invalid JSON' });
  }
  console.error('[Server] Unhandled error:', err?.message || err);
  res.status(500).json({ error: err?.message || 'Internal server error' });
});

const server = app.listen(PORT, () => {
  console.log(`JCL Tools server listening on http://127.0.0.1:${PORT}`);
});

// Prevent client disconnect socket errors (EOF/ECONNRESET/EPIPE) from crashing the server
server.on('connection', (socket) => {
  socket.on('error', (err) => {
    if (err && (err.code === 'EOF' || err.code === 'ECONNRESET' || err.code === 'EPIPE')) {
      console.warn('[Server] Ignored client socket error:', err.code);
      return;
    }
    console.error('[Server] Socket error:', err?.message || err);
  });
});
