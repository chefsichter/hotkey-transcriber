// ==UserScript==
// @name         ChatGPT Focus + Insert Prompt
// @namespace    hotkey-transcriber
// @version      1.1
// @description  Fokussiert ChatGPT, fuellt ht_prompt ein und zeigt ein Badge
// @match        https://chatgpt.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  const TEXTAREA_SELECTOR = 'textarea[name="prompt-textarea"]';
  const MAX_ATTEMPTS = 120;
  const DELAY_MS = 250;
  const BADGE_ID = 'ht-vm-badge';

  function showBadge(text, color = '#1f7a1f') {
    let badge = document.getElementById(BADGE_ID);

    if (!badge) {
      badge = document.createElement('div');
      badge.id = BADGE_ID;
      badge.style.position = 'fixed';
      badge.style.top = '16px';
      badge.style.right = '16px';
      badge.style.zIndex = '999999';
      badge.style.padding = '10px 14px';
      badge.style.borderRadius = '12px';
      badge.style.color = '#fff';
      badge.style.fontSize = '14px';
      badge.style.fontFamily = 'sans-serif';
      badge.style.boxShadow = '0 4px 14px rgba(0,0,0,0.25)';
      badge.style.pointerEvents = 'none';
      document.body.appendChild(badge);
    }

    badge.textContent = text;
    badge.style.background = color;
  }

  function hideBadgeLater(delay = 2500) {
    setTimeout(() => {
      const badge = document.getElementById(BADGE_ID);
      if (badge) {
        badge.remove();
      }
    }, delay);
  }

  function getTextarea() {
    return document.querySelector(TEXTAREA_SELECTOR);
  }

  function focusTextarea(textarea) {
    textarea.focus();
    if (document.activeElement !== textarea) {
      textarea.click();
      textarea.focus();
    }
  }

  function setNativeValue(element, value) {
    const prototype = Object.getPrototypeOf(element);
    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
    if (descriptor && typeof descriptor.set === 'function') {
      descriptor.set.call(element, value);
    } else {
      element.value = value;
    }
  }

  function insertPrompt(textarea, prompt) {
    setNativeValue(textarea, prompt);
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.dispatchEvent(new Event('change', { bubbles: true }));
    focusTextarea(textarea);
  }

  function clearPromptParam() {
    const url = new URL(window.location.href);
    if (!url.searchParams.has('ht_prompt')) {
      return;
    }
    url.searchParams.delete('ht_prompt');
    url.searchParams.delete('ht_submit');
    history.replaceState(null, '', url.toString());
  }

  function maybeSubmit() {
    const url = new URL(window.location.href);
    return url.searchParams.get('ht_submit') === '1';
  }

  function tryClickSubmit() {
    const button =
      document.querySelector('button[data-testid="send-button"]') ||
      document.querySelector('#composer-submit-button');

    if (button && !button.disabled) {
      button.click();
      showBadge('Prompt gesendet', '#7a4b1f');
      hideBadgeLater();
      return true;
    }
    return false;
  }

  function run() {
    showBadge('Script gestartet', '#245b99');

    const url = new URL(window.location.href);
    const prompt = url.searchParams.get('ht_prompt');

    if (!prompt) {
      const textarea = getTextarea();
      if (textarea) {
        focusTextarea(textarea);
        showBadge('Composer fokussiert');
        hideBadgeLater();
      } else {
        showBadge('Warte auf Composer...', '#666');
      }
      return;
    }

    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      const textarea = getTextarea();

      if (!textarea) {
        showBadge(`Warte auf Composer... (${attempts})`, '#666');
        if (attempts >= MAX_ATTEMPTS) {
          clearInterval(timer);
          showBadge('Composer nicht gefunden', '#a12b2b');
          hideBadgeLater(4000);
        }
        return;
      }

      focusTextarea(textarea);
      insertPrompt(textarea, prompt);
      showBadge('Prompt eingefuellt');

      if (maybeSubmit()) {
        setTimeout(() => {
          if (!tryClickSubmit()) {
            showBadge('Senden nicht bereit', '#a12b2b');
            hideBadgeLater(4000);
          }
        }, 150);
      } else {
        hideBadgeLater();
      }

      clearPromptParam();
      clearInterval(timer);
    }, DELAY_MS);
  }

  run();
})();
