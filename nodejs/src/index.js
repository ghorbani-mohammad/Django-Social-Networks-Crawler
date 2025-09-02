const express = require('express');
const { createServer } = require('http');
const { WebSocketServer } = require('ws');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
require('dotenv').config();

const { PrismaClient } = require('@prisma/client');
const logger = require('./logger');

// Get PUBLIC_API_KEY from environment
const PUBLIC_API_KEY = process.env.PUBLIC_API_KEY;

const app = express();
const httpServer = createServer(app);

// Create WebSocket server
const wss = new WebSocketServer({ 
  server: httpServer
});

// Add WebSocket server error handling
wss.on('error', (error) => {
  logger.error('WebSocket Server error:', error);
});

// Log all incoming HTTP upgrade requests
httpServer.on('upgrade', (request, socket, head) => {
  logger.info(`WebSocket upgrade request: ${request.method} ${request.url}`);
  logger.info(`Headers: ${JSON.stringify(request.headers)}`);
});

logger.info('WebSocket server initialized with path: /ws/');

const prisma = new PrismaClient();

// Middleware
app.use(helmet());
app.use(compression());
app.use(morgan('combined', { stream: logger.stream }));
app.use(cors({
  origin: 'https://social.m-gh.com',
  credentials: true
}));
app.use(express.json());

// Add comprehensive request logging middleware
app.use((req, res, next) => {
  logger.info(`Incoming request: ${req.method} ${req.url} - Headers: ${JSON.stringify(req.headers)}`);
  next();
});

// Add a catch-all route to log unhandled requests
app.use('*', (req, res, next) => {
  if (req.url.includes('socket.io')) {
    logger.info(`Socket.IO request detected: ${req.method} ${req.url}`);
  }
  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  logger.info('Health check requested');
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// WebSocket test endpoint
app.get('/ws/test', (req, res) => {
  logger.info('WebSocket test endpoint requested');
  res.json({ message: 'WebSocket server is running', path: '/ws/' });
});

// Store active connections
const connections = new Map();

// WebSocket connection handling
wss.on('connection', async (ws, request) => {
  const connectionId = Math.random().toString(36).substr(2, 9);
  connections.set(connectionId, { ws, userId: null });
  
  logger.info(`Client connected: ${connectionId}`);

  ws.on('message', async (message) => {
    try {
      const data = JSON.parse(message.toString());
      logger.info(`Received message: ${JSON.stringify(data)}`);

      switch (data.type) {
        case 'authenticate':
          const { userId, apiKey } = data;
          
          if (!userId || !apiKey) {
            ws.send(JSON.stringify({ type: 'error', message: 'User ID and API key are required' }));
            return;
          }

          // Validate API key
          if (apiKey !== PUBLIC_API_KEY) {
            ws.send(JSON.stringify({ type: 'error', message: 'Invalid API key' }));
            logger.warn(`Authentication failed for user ${userId}: Invalid API key`);
            return;
          }

          // Store connection in database (simple tracking)
          try {
            await prisma.webSocketConnection.create({
              data: {
                user_id: userId,
                socket_id: connectionId,
                is_active: true
              }
            });
          } catch (error) {
            // If table doesn't exist, just continue without DB storage
            logger.warn('WebSocket connection table not found, continuing without DB storage');
          }

          // Update connection info
          connections.set(connectionId, { ws, userId });
          
          ws.send(JSON.stringify({ type: 'authenticated', message: 'Successfully authenticated' }));
          logger.info(`User ${userId} authenticated with connection ${connectionId}`);
          break;

        case 'job_update':
          // For now, we're only reading from Django DB, not updating
          ws.send(JSON.stringify({ 
            type: 'error', 
            message: 'Job updates not supported in read-only mode' 
          }));
          break;

        default:
          ws.send(JSON.stringify({ type: 'error', message: 'Unknown message type' }));
      }
    } catch (error) {
      logger.error('Message handling error:', error);
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid message format' }));
    }
  });

  ws.on('close', async () => {
    try {
      // Mark connection as inactive in database
      try {
        await prisma.webSocketConnection.updateMany({
          where: { socket_id: connectionId },
          data: { is_active: false }
        });
      } catch (error) {
        // If table doesn't exist, just continue
        logger.warn('WebSocket connection table not found for cleanup');
      }

      connections.delete(connectionId);
      logger.info(`Client disconnected: ${connectionId}`);
    } catch (error) {
      logger.error('Disconnection error:', error);
    }
  });

  ws.on('error', (error) => {
    logger.error('WebSocket error:', error);
  });
});

// API endpoint for job notifications (called from Django)
app.post('/api/notify-job', async (req, res) => {
  try {
    const { userId, job } = req.body;
    
    if (!userId || !job) {
      return res.status(400).json({ error: 'userId and job data are required' });
    }

    // Notify user about new job
    const message = {
      type: 'new_job',
      job,
      timestamp: new Date().toISOString()
    };

    // Send to all connections for this user
    let notificationsSent = 0;
    connections.forEach((conn, id) => {
      if (conn.userId === userId && conn.ws.readyState === 1) {
        conn.ws.send(JSON.stringify(message));
        notificationsSent++;
      }
    });

    logger.info(`Job notification sent to ${notificationsSent} connections for user ${userId}: ${job.title}`);
    res.json({ success: true, notificationsSent });
  } catch (error) {
    logger.error('Job notification error:', error);
    res.status(500).json({ error: 'Failed to send job notification' });
  }
});

// Get recent jobs from Django database
app.get('/api/jobs/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    
    // Read from existing Django LinkedIn jobs table
    const jobs = await prisma.linkedinJob.findMany({
      where: { 
        eligible: true,
        // You can add more filters here based on your needs
      },
      orderBy: { created_at: 'desc' },
      take: 50 // Limit to recent 50 jobs
    });

    logger.info(`Recent jobs retrieved: ${jobs.length} jobs`);
    res.json(jobs);
  } catch (error) {
    logger.error('Get jobs error:', error);
    res.status(500).json({ error: 'Failed to get jobs' });
  }
});

// Error handling middleware
app.use((err, req, res, next) => {
  logger.error('Unhandled error:', err);
  res.status(500).json({ error: 'Something went wrong!' });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully');
  await prisma.$disconnect();
  process.exit(0);
});

process.on('SIGINT', async () => {
  logger.info('SIGINT received, shutting down gracefully');
  await prisma.$disconnect();
  process.exit(0);
});

const PORT = process.env.PORT || 3000;

httpServer.listen(PORT, () => {
  logger.info(`WebSocket service started successfully on port ${PORT}`);
});
