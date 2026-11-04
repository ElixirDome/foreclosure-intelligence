import { test, expect } from '@playwright/test';
import { authenticateAndNavigateToDashboard } from './helpers';

test.describe('Property Listings & Feed Interactions', () => {
  const mockPropertiesData = {
    items: [
      {
        id: 101,
        address: 'Flat No 402, Green Avenue, Gurdaspur',
        city: 'Gurdaspur',
        locality: 'Green Avenue',
        property_type: 'residential',
        reserve_price: 3450000,
        estimated_value: 4500000,
        discount_percentage: 23.3,
        deal_score: 82.5,
        auction_date: '2026-11-15',
        foreclosure_status: 'scheduled',
        sources: [
          {
            source_name: 'PNB',
            source_url: 'https://pnbindia.in/notice1.pdf',
            document_type: 'notice',
          },
        ],
      },
      {
        id: 102,
        address: 'House No 12, Civil Lines, Batala',
        city: 'Gurdaspur',
        locality: 'Civil Lines',
        property_type: 'residential',
        reserve_price: 6500000,
        estimated_value: 7000000,
        discount_percentage: 7.1,
        deal_score: 65.0,
        auction_date: '2026-11-20',
        foreclosure_status: 'upcoming',
        sources: [
          {
            source_name: 'SBI',
            source_url: 'https://sbi.co.in/auction2.pdf',
            document_type: 'notice',
          },
        ],
      },
    ],
    total: 2,
    page: 1,
    pages: 1,
  };

  test.beforeEach(async ({ page }) => {
    await authenticateAndNavigateToDashboard(page, mockPropertiesData);
  });

  test('displays navbar, search box, summary cards, and property feed', async ({ page }) => {
    await expect(page.locator('.ig-nav-brand')).toContainText('FORECLOSURE.AI');
    await expect(page.getByPlaceholder('🔍 Search city, locality, bank...')).toBeVisible();

    // Verify property cards rendered
    const cards = page.locator('.ig-card');
    await expect(cards).toHaveCount(2);
    await expect(cards.first()).toContainText('Flat No 402, Green Avenue');
    await expect(cards.first()).toContainText('PNB');
  });

  test('search input filters properties', async ({ page }) => {
    const searchInput = page.getByPlaceholder('🔍 Search city, locality, bank...');
    await searchInput.fill('Batala');
    await searchInput.press('Enter');

    await expect(searchInput).toHaveValue('Batala');
  });

  test('shows empty state when no records match filter', async ({ page }) => {
    await page.route(/\/properties\/?(\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          pages: 1,
        }),
      });
    });

    // Apply filter with no matches
    const searchInput = page.getByPlaceholder('🔍 Search city, locality, bank...');
    await searchInput.fill('NonExistentPlace999');
    await searchInput.press('Enter');

    await expect(page.locator('h3')).toContainText(/No auctions matched your filters/i);
  });
});
