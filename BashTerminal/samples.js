// src/components/TerminalExamples.js
// Export terminal component examples for use in MDX files

import React from "react";
import BashTerminal from "./index";

// Basic usage - Interactive terminal
export const InteractiveTerminal = () => <BashTerminal />;

// Pre-populated with commands - Read-only
export const ReadOnlyTerminal = () => (
  <BashTerminal
    initialCommands={[
      { command: "pwd", output: "/home/user/project" },
      {
        command: "ls -la",
        output: `total 12
drwxr-xr-x 3 user user 4096 Jul 21 10:30 .
drwxr-xr-x 5 user user 4096 Jul 21 10:25 ..
-rw-r--r-- 1 user user  234 Jul 21 10:30 README.md
-rw-r--r-- 1 user user  567 Jul 21 10:30 package.json
drwxr-xr-x 2 user user 4096 Jul 21 10:30 src`,
      },
      {
        command: "cat package.json",
        output: `{
  "name": "my-project",
  "version": "1.0.0",
  "description": "A sample project",
  "main": "index.js"
}`,
      },
    ]}
    readOnly={true}
    title="Project Setup"
    height="300px"
  />
);

// Custom configuration
export const CustomTerminal = () => (
  <BashTerminal
    title="production-server"
    prompt="admin@prod:~/app$ "
    height="500px"
    initialCommands={[
      {
        command: "docker ps",
        output:
          'CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS   PORTS   NAMES\n123456789abc   nginx     "/docker-entrypoint.sh"   2 hours ago   Up 2 hours   0.0.0.0:80->80/tcp   web-server',
      },
    ]}
  />
);
