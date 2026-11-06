import { test, expect } from '@playwright/test';

test.describe('Authentication & Onboarding Flow', () => {
  test('login page loads with brand header and quick sign-in buttons', async ({ page }) => {
    await page.goto('/login');

    await expect(page.locator('.ig-brand-badge')).toContainText('FORECLOSURE INTELLIGENCE');
    await expect(page.locator('h1')).toContainText('Welcome back');

    const adminDemoBtn = page.getByRole('button', { name: 'Demo Admin' });
    const userDemoBtn = page.getByRole('button', { name: 'Demo User' });
    await expect(adminDemoBtn).toBeVisible();
    await expect(userDemoBtn).toBeVisible();
  });

  test('clicking demo button pre-fills credentials', async ({ page }) => {
    await page.goto('/login');

    await page.getByRole('button', { name: 'Demo Admin' }).click();

    const emailInput = page.getByPlaceholder('Email address');
    const passwordInput = page.getByPlaceholder('Password');

    await expect(emailInput).toHaveValue('test1@example.com');
    await expect(passwordInput).toHaveValue('password123');
  });

  test('shows error message on invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.route('**/auth/login', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid email or password.' }),
      });
    });

    await page.getByPlaceholder('Email address').fill('nonexistent@example.com');
    await page.getByPlaceholder('Password').fill('wrongpassword');
    await page.getByRole('button', { name: 'Sign In to Desk' }).click();

    const errorBanner = page.locator('.ig-error-banner');
    await expect(errorBanner).toBeVisible();
    await expect(errorBanner).toContainText('Invalid email or password.');
  });

  test('successful login navigates to dashboard and stores token', async ({ page }) => {
    await page.goto('/login');

    await page.route('**/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'fake-jwt-token-12345',
          token_type: 'bearer',
        }),
      });
    });

    await page.route('**/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          email: 'test@example.com',
          role: 'user',
        }),
      });
    });

    await page.route('**/properties/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/properties/summary', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_properties: 10,
          residential: 8,
          commercial: 2,
          upcoming_auctions: 5,
          properties_with_estimates: 4,
        }),
      });
    });

    await page.getByRole('button', { name: 'Demo User' }).click();
    await page.getByRole('button', { name: 'Sign In to Desk' }).click();

    await page.waitForURL('**/dashboard');
    expect(page.url()).toContain('/dashboard');
  });
});
