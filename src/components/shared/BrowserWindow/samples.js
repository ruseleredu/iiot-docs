// src/components/BrowserExamples.js
// Export browser component examples for use in MDX files

import React from "react";
import WebBrowser from "./WebBrowser";

// Basic static browser
export const BasicBrowser = () => (
  <WebBrowser
    url="https://docusaurus.io"
    title="Documentation Browser"
    height="500px"
  />
);

// Interactive browser with navigation
export const InteractiveBrowser = () => (
  <WebBrowser
    url="https://example.com"
    title="Interactive Browser"
    height="600px"
    interactive={true}
    showNavigation={true}
    showAddressBar={true}
  />
);

// Browser with custom mock content
export const MockContentBrowser = () => (
  <WebBrowser
    title="Sample Website"
    height="500px"
    showNavigation={false}
    showAddressBar={false}
    mockData={{
      title: "Welcome to Our Platform",
      subtitle: "Build amazing applications with our tools",
      sections: [
        {
          title: "Getting Started",
          content:
            "Our platform provides everything you need to build modern web applications. Start with our comprehensive documentation and examples.",
        },
        {
          title: "Features",
          content:
            "Includes authentication, database integration, real-time updates, and deployment tools. Scale from prototype to production seamlessly.",
        },
        {
          title: "Community",
          content:
            "Join thousands of developers building with our platform. Get help, share ideas, and contribute to our open source projects.",
        },
      ],
    }}
  />
);

// Mobile-friendly browser
export const MobileBrowser = () => (
  <WebBrowser
    url="https://m.example.com"
    title="Mobile View"
    height="400px"
    showNavigation={true}
    showAddressBar={true}
  />
);

// Browser with custom content component
export const CustomContentBrowser = () => (
  <WebBrowser
    title="API Documentation"
    height="450px"
    showNavigation={false}
    content={
      <div style={{ padding: "24px", fontFamily: "system-ui" }}>
        <h1 style={{ color: "#1a73e8", marginBottom: "24px" }}>
          API Reference
        </h1>
        <div style={{ marginBottom: "32px" }}>
          <h2 style={{ color: "#333", marginBottom: "16px" }}>
            Authentication
          </h2>
          <div
            style={{
              backgroundColor: "#f8f9fa",
              padding: "16px",
              borderRadius: "8px",
              borderLeft: "4px solid #1a73e8",
              fontFamily: "Monaco, monospace",
              fontSize: "14px",
            }}
          >
            POST /api/auth/login
            <br />
            Content-Type: application/json
            <br />
            <br />
            {`{
  "email": "user@example.com",
  "password": "securepassword"
}`}
          </div>
        </div>
        <div>
          <h2 style={{ color: "#333", marginBottom: "16px" }}>Response</h2>
          <div
            style={{
              backgroundColor: "#e8f5e8",
              padding: "16px",
              borderRadius: "8px",
              borderLeft: "4px solid #28a745",
              fontFamily: "Monaco, monospace",
              fontSize: "14px",
            }}
          >
            {`{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe"
  }
}`}
          </div>
        </div>
      </div>
    }
  />
);

// Minimal browser without navigation
export const MinimalBrowser = () => (
  <WebBrowser
    url="https://example.com"
    title="Minimal Browser"
    height="300px"
    showNavigation={false}
    showAddressBar={false}
  />
);
