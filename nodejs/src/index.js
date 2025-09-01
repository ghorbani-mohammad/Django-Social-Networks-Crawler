const express = require('express');
const { createServer } = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
require('dotenv').config();

const { PrismaClient } = require('@prisma/client');

const app = express();
const httpServer = createServer(app);
const io = new Server(httpServer, {
  path: '/ws/',
  cors: {
    origin: process.env.FRONTEND_URL || 'http://localhost:3000',
    methods: ['GET', 'POST'],
    credentials: true
  }
});

const prisma = new PrismaClient();

// Middleware
app.use(helmet());
app.use(compression());
app.use(morgan('combined'));
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true
}));
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// WebSocket connection handling
io.on('connection', async (socket) => {
  console.log(`Client connected: ${socket.id}`);

  // Handle user authentication
  socket.on('authenticate', async (data) => {
    try {
      const { userId } = data;
      
      if (!userId) {
        socket.emit('error', { message: 'User ID is required' });
        return;
      }

      // Store connection in database
      await prisma.connection.create({
        data: {
          userId,
          socketId: socket.id,
          isActive: true
        }
      });

      // Join user-specific room
      socket.join(`user_${userId}`);
      socket.emit('authenticated', { message: 'Successfully authenticated' });
      
      console.log(`User ${userId} authenticated with socket ${socket.id}`);
    } catch (error) {
      console.error('Authentication error:', error);
      socket.emit('error', { message: 'Authentication failed' });
    }
  });

  // Handle job status updates
  socket.on('job_update', async (data) => {
    try {
      const { jobId, status, userId } = data;
      
      // Update job status in database
      await prisma.job.update({
        where: { id: jobId },
        data: { status }
      });

      // Notify all connections of the user about the job update
      io.to(`user_${userId}`).emit('job_status_changed', {
        jobId,
        status,
        timestamp: new Date().toISOString()
      });

      console.log(`Job ${jobId} status updated to ${status} for user ${userId}`);
    } catch (error) {
      console.error('Job update error:', error);
      socket.emit('error', { message: 'Failed to update job status' });
    }
  });

  // Handle disconnection
  socket.on('disconnect', async () => {
    try {
      // Mark connection as inactive in database
      await prisma.connection.updateMany({
        where: { socketId: socket.id },
        data: { isActive: false }
      });

      console.log(`Client disconnected: ${socket.id}`);
    } catch (error) {
      console.error('Disconnection error:', error);
    }
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
    io.to(`user_${userId}`).emit('new_job', {
      job,
      timestamp: new Date().toISOString()
    });

    res.json(job);
  } catch (error) {
    console.error('Create job error:', error);
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

    res.json(jobs);
  } catch (error) {
    console.error('Get jobs error:', error);
    res.status(500).json({ error: 'Failed to get jobs' });
  }
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully');
  await prisma.$disconnect();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, shutting down gracefully');
  await prisma.$disconnect();
  process.exit(0);
});

const PORT = process.env.PORT || 3000;

httpServer.listen(PORT, () => {
  console.log(`WebSocket service running on port ${PORT}`);
});
