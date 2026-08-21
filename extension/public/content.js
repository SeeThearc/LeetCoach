// Content script — injected into LeetCode problem pages.
// Extracts problem info from the page when the side panel asks for it.

function getProblemSlug() {
  // URL looks like: leetcode.com/problems/two-sum/description
  const match = window.location.pathname.match(/\/problems\/([^/]+)/);
  return match ? match[1] : null;
}

function getLanguage() {
  // LeetCode shows the selected language in a button
  const btn = document.querySelector('button[id^="headlessui-listbox-button"]');
  if (btn) return btn.textContent.trim().toLowerCase();
  // Fallback: check the URL or default
  return 'cpp';
}

function getUserCode() {
  // Try to grab code from Monaco editor's DOM
  try {
    const lines = document.querySelectorAll('.view-lines .view-line');
    if (lines.length > 0) {
      return Array.from(lines).map(l => l.textContent).join('\n');
    }
  } catch (e) { /* ignore */ }
  return '';
}

// Listen for requests from the side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_PROBLEM_DATA') {
    sendResponse({
      slug: getProblemSlug(),
      language: getLanguage(),
      code: getUserCode(),
    });
  }
  return true;
});
