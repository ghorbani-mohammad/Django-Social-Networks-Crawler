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
          const { userId } = data;
          
          if (!userId) {
            ws.send(JSON.stringify({ type: 'error', message: 'User ID is required' }));
            return;
          }

          // Store connection in database
          await prisma.connection.create({
            data: {
              userId,
              socketId: connectionId,
              isActive: true
            }
          });

          // Update connection info
          connections.set(connectionId, { ws, userId });
          
          ws.send(JSON.stringify({ type: 'authenticated', message: 'Successfully authenticated' }));
          logger.info(`User ${userId} authenticated with connection ${connectionId}`);
          break;

        case 'job_update':
          const { jobId, status, userId: updateUserId } = data;
          
          // Update job status in database
          await prisma.job.update({
            where: { id: jobId },
            data: { status }
          });

          // Notify all connections of the user about the job update
          const message = {
            type: 'job_status_changed',
            jobId,
            status,
            timestamp: new Date().toISOString()
          };

          // Send to all connections for this user
          connections.forEach((conn, id) => {
            if (conn.userId === updateUserId && conn.ws.readyState === 1) {
              conn.ws.send(JSON.stringify(message));
            }
          });

          logger.info(`Job ${jobId} status updated to ${status} for user ${updateUserId}`);
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
      await prisma.connection.updateMany({
        where: { socketId: connectionId },
        data: { isActive: false }
      });

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

// API endpoints for job management
app.post('/api/jobs', async (req, res) => {
  try {
    const { title, description, userId } = req.body;
    
    const job = await prisma.job.create({
      data: {
        title,
        description,
        userId
      }
    });

    // Notify user about new job
    const message = {
      type: 'new_job',
      job,
      timestamp: new Date().toISOString()
    };

    // Send to all connections for this user
    connections.forEach((conn, id) => {
      if (conn.userId === userId && conn.ws.readyState === 1) {
        conn.ws.send(JSON.stringify(message));
      }
    });

    logger.info(`New job created: ${job.id} for user ${userId}`);
    res.json(job);
  } catch (error) {
    logger.error('Create job error:', error);
    res.status(500).json({ error: 'Failed to create job' });
  }
});

app.get('/api/jobs/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    
    const jobs = await prisma.job.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' }
    });

    logger.info(`Jobs retrieved for user ${userId}: ${jobs.length} jobs`);
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
