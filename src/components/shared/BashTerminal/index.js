import React, { useState, useRef, useEffect } from "react";
import styles from "./styles.module.css";

const BashTerminal = ({
  initialCommands = [],
  title = "bash",
  height = "400px",
  prompt = "user@localhost:~$ ",
  readOnly = false,
}) => {
  const [history, setHistory] = useState([]);
  const [currentInput, setCurrentInput] = useState("");
  const [commandHistory, setCommandHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const inputRef = useRef(null);
  const terminalRef = useRef(null);

  // Initialize with any provided commands
  useEffect(() => {
    if (initialCommands.length > 0) {
      const initialHistory = initialCommands
        .map((cmd) => ({
          type: "command",
          content: `${prompt}${cmd.command}`,
          timestamp: Date.now(),
        }))
        .concat(
          initialCommands.map((cmd) => ({
            type: "output",
            content: cmd.output || "",
            timestamp: Date.now(),
          })),
        )
        .flat();
      setHistory(initialHistory);
    }
  }, [initialCommands, prompt]);

  // Auto-scroll to bottom when history updates
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [history]);

  const executeCommand = (command) => {
    const cmd = command.trim();

    // Add command to history
    setHistory((prev) => [
      ...prev,
      {
        type: "command",
        content: `${prompt}${cmd}`,
        timestamp: Date.now(),
      },
    ]);

    // Add to command history for up/down navigation
    setCommandHistory((prev) => [...prev, cmd]);
    setHistoryIndex(-1);

    // Simple command simulation
    let output = "";
    switch (cmd.toLowerCase()) {
      case "ls":
        output =
          "Documents  Downloads  Pictures  Videos  README.md  package.json";
        break;
      case "pwd":
        output = "/home/user";
        break;
      case "whoami":
        output = "user";
        break;
      case "date":
        output = new Date().toString();
        break;
      case "clear":
        setHistory([]);
        return;
      case "help":
        output = `Available commands:
ls      - list directory contents
pwd     - print working directory
whoami  - display current username
date    - display current date and time
clear   - clear terminal screen
help    - show this help message`;
        break;
      case "":
        // Empty command, just show new prompt
        break;
      default:
        if (cmd.startsWith("echo ")) {
          output = cmd.substring(5);
        } else {
          output = `bash: ${cmd}: command not found`;
        }
    }

    if (output) {
      setHistory((prev) => [
        ...prev,
        {
          type: "output",
          content: output,
          timestamp: Date.now(),
        },
      ]);
    }
  };

  const handleKeyDown = (e) => {
    if (readOnly) return;

    if (e.key === "Enter") {
      executeCommand(currentInput);
      setCurrentInput("");
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (commandHistory.length > 0) {
        const newIndex =
          historyIndex < commandHistory.length - 1
            ? historyIndex + 1
            : historyIndex;
        setHistoryIndex(newIndex);
        setCurrentInput(
          commandHistory[commandHistory.length - 1 - newIndex] || "",
        );
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setCurrentInput(
          commandHistory[commandHistory.length - 1 - newIndex] || "",
        );
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCurrentInput("");
      }
    }
  };

  const focusTerminal = () => {
    if (!readOnly && inputRef.current) {
      inputRef.current.focus();
    }
  };

  return (
    <div className={styles.terminal} style={{ height }}>
      <div className={styles.terminalHeader}>
        <div className={styles.terminalButtons}>
          <span
            className={styles.terminalButton}
            style={{ backgroundColor: "#ff5f56" }}
          ></span>
          <span
            className={styles.terminalButton}
            style={{ backgroundColor: "#ffbd2e" }}
          ></span>
          <span
            className={styles.terminalButton}
            style={{ backgroundColor: "#27ca3f" }}
          ></span>
        </div>
        <div className={styles.terminalTitle}>{title}</div>
        <div></div>
      </div>

      <div
        className={styles.terminalBody}
        onClick={focusTerminal}
        ref={terminalRef}
      >
        {history.map((entry, index) => (
          <div key={index} className={styles[entry.type]}>
            {entry.content.split("\n").map((line, lineIndex) => (
              <div key={lineIndex}>{line}</div>
            ))}
          </div>
        ))}

        {!readOnly && (
          <div className={styles.inputLine}>
            <span className={styles.prompt}>{prompt}</span>
            <input
              ref={inputRef}
              type="text"
              value={currentInput}
              onChange={(e) => setCurrentInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className={styles.terminalInput}
              autoFocus
              spellCheck={false}
              autoComplete="off"
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default BashTerminal;
