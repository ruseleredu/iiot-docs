import React, { useState, useRef, useEffect } from "react";
import styles from "./WebBrowser.module.css";

const WebBrowser = ({
  url = "https://example.com",
  title = "Web Browser",
  height = "600px",
  showNavigation = true,
  showAddressBar = true,
  interactive = false,
  content = null,
  mockData = null,
}) => {
  const [currentUrl, setCurrentUrl] = useState(url);
  const [inputUrl, setInputUrl] = useState(url);
  const [loading, setLoading] = useState(false);
  const [canGoBack, setCanGoBack] = useState(false);
  const [canGoForward, setCanGoForward] = useState(false);
  const [history, setHistory] = useState([url]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const iframeRef = useRef(null);

  useEffect(() => {
    setCurrentUrl(url);
    setInputUrl(url);
  }, [url]);

  const navigateTo = (newUrl) => {
    if (!interactive) return;

    setLoading(true);
    setTimeout(() => setLoading(false), 1000);

    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(newUrl);
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setCurrentUrl(newUrl);
    setInputUrl(newUrl);
    setCanGoBack(newHistory.length > 1);
    setCanGoForward(false);
  };

  const goBack = () => {
    if (canGoBack && interactive) {
      const newIndex = historyIndex - 1;
      setHistoryIndex(newIndex);
      setCurrentUrl(history[newIndex]);
      setInputUrl(history[newIndex]);
      setCanGoBack(newIndex > 0);
      setCanGoForward(true);
    }
  };

  const goForward = () => {
    if (canGoForward && interactive) {
      const newIndex = historyIndex + 1;
      setHistoryIndex(newIndex);
      setCurrentUrl(history[newIndex]);
      setInputUrl(history[newIndex]);
      setCanGoForward(newIndex < history.length - 1);
      setCanGoBack(true);
    }
  };

  const refresh = () => {
    if (!interactive) return;

    setLoading(true);
    setTimeout(() => setLoading(false), 800);
  };

  const handleAddressSubmit = (e) => {
    e.preventDefault();
    if (!interactive) return;

    let processedUrl = inputUrl.trim();
    if (
      !processedUrl.startsWith("http://") &&
      !processedUrl.startsWith("https://")
    ) {
      processedUrl = "https://" + processedUrl;
    }
    navigateTo(processedUrl);
  };

  const renderMockContent = () => {
    if (content) {
      return <div className={styles.customContent}>{content}</div>;
    }

    if (mockData) {
      return (
        <div className={styles.mockPage}>
          <div className={styles.mockHeader}>
            <h1>{mockData.title || "Sample Website"}</h1>
            {mockData.subtitle && (
              <p className={styles.subtitle}>{mockData.subtitle}</p>
            )}
          </div>
          <div className={styles.mockBody}>
            {mockData.sections?.map((section, index) => (
              <div key={index} className={styles.mockSection}>
                <h2>{section.title}</h2>
                <p>{section.content}</p>
              </div>
            )) || (
              <div className={styles.mockSection}>
                <h2>Welcome to our website</h2>
                <p>
                  This is a sample page demonstrating the web browser component.
                  You can customize the content by passing mockData or content
                  props.
                </p>
                <div className={styles.mockButtons}>
                  <button className={styles.mockButton}>Get Started</button>
                  <button className={styles.mockButtonSecondary}>
                    Learn More
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      );
    }

    // Default iframe content
    try {
      return (
        <iframe
          ref={iframeRef}
          src={currentUrl}
          className={styles.browserFrame}
          title="Browser Content"
          sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
        />
      );
    } catch (error) {
      return (
        <div className={styles.errorContent}>
          <h2>Unable to load content</h2>
          <p>This site cannot be displayed in an iframe.</p>
          <p>URL: {currentUrl}</p>
        </div>
      );
    }
  };

  return (
    <div className={styles.browser} style={{ height }}>
      {/* Browser Header */}
      <div className={styles.browserHeader}>
        <div className={styles.windowControls}>
          <span
            className={styles.windowButton}
            style={{ backgroundColor: "#ff5f56" }}
          ></span>
          <span
            className={styles.windowButton}
            style={{ backgroundColor: "#ffbd2e" }}
          ></span>
          <span
            className={styles.windowButton}
            style={{ backgroundColor: "#27ca3f" }}
          ></span>
        </div>
        <div className={styles.browserTitle}>{title}</div>
        <div className={styles.browserMenus}>
          <span className={styles.menuDots}>⋯</span>
        </div>
      </div>

      {/* Navigation Bar */}
      {showNavigation && (
        <div className={styles.navigationBar}>
          <div className={styles.navButtons}>
            <button
              className={`${styles.navButton} ${!canGoBack || !interactive ? styles.disabled : ""}`}
              onClick={goBack}
              disabled={!canGoBack || !interactive}
              title="Go back"
            >
              ←
            </button>
            <button
              className={`${styles.navButton} ${!canGoForward || !interactive ? styles.disabled : ""}`}
              onClick={goForward}
              disabled={!canGoForward || !interactive}
              title="Go forward"
            >
              →
            </button>
            <button
              className={`${styles.navButton} ${!interactive ? styles.disabled : ""}`}
              onClick={refresh}
              disabled={!interactive}
              title="Refresh"
            >
              {loading ? "⟳" : "↻"}
            </button>
          </div>

          {showAddressBar && (
            <form className={styles.addressBar} onSubmit={handleAddressSubmit}>
              <div className={styles.securityIcon}>🔒</div>
              <input
                type="text"
                className={styles.addressInput}
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                placeholder="Enter URL or search term"
                readOnly={!interactive}
              />
              {interactive && (
                <button type="submit" className={styles.goButton}>
                  Go
                </button>
              )}
            </form>
          )}

          <div className={styles.browserActions}>
            <button className={styles.actionButton} title="Bookmark">
              ⭐
            </button>
            <button className={styles.actionButton} title="Menu">
              ⋯
            </button>
          </div>
        </div>
      )}

      {/* Browser Content */}
      <div className={styles.browserContent}>
        {loading && (
          <div className={styles.loadingBar}>
            <div className={styles.loadingProgress}></div>
          </div>
        )}
        {renderMockContent()}
      </div>
    </div>
  );
};

export default WebBrowser;
