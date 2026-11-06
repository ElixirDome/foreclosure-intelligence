import { test, expect } from '@playwright/test';
import { authenticateAndNavigateToDashboard } from './helpers';

test.describe('Real-Time Live Updates & Indicator', () => {
  test.beforeEach(async ({ page }) => {
    await authenticateAndNavigateToDashboard(page);
  });

  test('displays real-time status indicator pill on dashboard', async ({ page }) => {
    const livePill = page.locator('.ig-live-pill');
    await expect(livePill).toBeVisible();

    const text = await livePill.innerText();
    expect(['live feed', 'polling', 'reconnecting']).toContain(text.trim().toLowerCase());
  });
});
