import { test, expect } from '@playwright/test';
import { authenticateAndNavigateToDashboard } from './helpers';

test.describe('Responsive Viewport Verification', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
    await authenticateAndNavigateToDashboard(page);
  });

  test('renders properly on Desktop (1280x800)', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    await expect(page.locator('.ig-navbar')).toBeVisible();
    await expect(page.locator('.ig-nav-brand')).toBeVisible();
    await expect(page.getByPlaceholder('🔍 Search city, locality, bank...')).toBeVisible();
    await expect(page.locator('.banknet-kpi-grid')).toBeVisible();
  });

  test('adapts layout for Tablet (768x1024)', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });

    await expect(page.locator('.ig-navbar')).toBeVisible();
    await expect(page.locator('.ig-nav-brand')).toBeVisible();
    await expect(page.locator('.banknet-kpi-grid')).toBeVisible();
  });

  test('adapts layout for Mobile (375x667)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    await expect(page.locator('.ig-navbar')).toBeVisible();
    await expect(page.locator('.ig-nav-brand')).toBeVisible();
    await expect(page.getByPlaceholder('🔍 Search city, locality, bank...')).toBeVisible();
  });
});
