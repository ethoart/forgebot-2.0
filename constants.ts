import { N8nConfig } from './types';

// CONFIGURATION
// ------------------------------------------------------------------
// ARCHITECTURE (PYTHON SERVER):
// Frontend (Nginx) -> Proxy /api/* -> Python Backend -> Mongo/WAHA
// ------------------------------------------------------------------

export const APP_CONFIG: N8nConfig = {
  useMockMode: false, 
  
  // Nginx proxies '/api' to the Python backend container
  apiBaseUrl: "/api",

  // Not used in this architecture, but kept for type compatibility
  n8nWebhookUrl: "/api", 
};

export const MOTIVATIONAL_QUOTES = [
  "Great work! You're making customers happy.",
  "Keep up the momentum!",
  "Another video delivered, another memory shared.",
  "Efficiency is doing better what is already being done.",
  "Your speed is impressive today!",
  "Technology is best when it brings people together.",
  "You are crushing the queue!",
];