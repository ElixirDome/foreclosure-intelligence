import { Page } from '@playwright/test';

/**
 * Standard test helper to authenticate through the UI and transition
 * to the dashboard cleanly via client-side routing.
 */
export async function authenticateAndNavigateToDashboard(page: Page, propertiesData?: any) {
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
      body: JSON.stringify({ id: 1, email: 'test@example.com', role: 'user' }),
    });
  });

  await page.route('**/auth/me/preferences', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ state: 'Punjab', district: 'Gurdaspur', onboarding_completed: true }),
    });
  });

  await page.route('**/properties/summary', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_properties: propertiesData?.items?.length || 12,
        residential: propertiesData?.items?.length || 10,
        commercial: 2,
        upcoming_auctions: 4,
        properties_with_estimates: 6,
      }),
    });
  });

  // Mock SSE stream with valid text/event-stream response
  await page.route('**/properties/stream*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
      body: ': ping\n\n',
    });
  });

  await page.route(/\/properties\/?(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        propertiesData || {
          items: [],
          total: 0,
          page: 1,
          pages: 1,
        }
      ),
    });
  });

  await page.goto('/login');
  await page.getByRole('button', { name: 'Demo User' }).click();
  await page.getByRole('button', { name: 'Sign In to Desk' }).click();
  await page.waitForURL('**/dashboard');
}
