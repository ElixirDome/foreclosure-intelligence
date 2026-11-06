import '@testing-library/jest-dom';
import { vi } from 'vitest';

// jsdom does not implement Element.prototype.scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();
