import { test, expect } from '@playwright/test';
import { authenticateAndNavigateToDashboard } from './helpers';

test.describe('Research Analyst RAG Chat Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock RAG endpoint to avoid external LLM latency
    await page.route('**/documents/rag*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          question: 'What are the upcoming auctions in Gurdaspur?',
          answer: 'Found active residential auctions in Gurdaspur with reserve prices under 40 Lakh.',
          citations: [
            {
              title: 'Official Auction Notice PDF',
              source_id: '/documents/501/file',
              kind: 'action',
              excerpt: 'Auction notice for Gurdaspur',
              score: 0.95,
            },
          ],
          structured: {
            summary: 'Gurdaspur auction opportunities',
            strengths: ['Clear title', 'SARFAESI compliant'],
            risks: ['Check municipal tax dues'],
            due_diligence: ['Inspect physical boundary'],
            recommendation: 'Good opportunity',
            deal_score: 82.0,
            deal_rating: 'Good',
          },
          context_kinds: ['document'],
          property_ids: [101],
          document_ids: [501],
          chunks_used: 1,
          method: 'rag',
          mode: 'targeted',
        }),
      });
    });

    await authenticateAndNavigateToDashboard(page);
  });

  test('opens analyst drawer, accepts user query, and renders structured answer', async ({ page }) => {
    // 1. Click floating analyst trigger
    const triggerBtn = page.getByTitle(/Open Research Analyst/i);
    await expect(triggerBtn).toBeVisible({ timeout: 10000 });
    await triggerBtn.click({ force: true });

    // 2. Analyst drawer opens
    const drawer = page.locator('.analyst-drawer');
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText('Research Analyst');

    // 3. Ask question
    const chatInput = drawer.getByPlaceholder(/Ask about auctions/i);
    await chatInput.fill('What are the upcoming auctions in Gurdaspur?');
    await chatInput.press('Enter');

    // 4. Verify assistant response rendered
    await expect(drawer.locator('.analyst-msg-row.assistant').nth(1)).toBeVisible({ timeout: 10000 });
    const content = await drawer.innerText();
    expect(content.toLowerCase()).toContain('gurdaspur');

    // 5. Verify action pill or source citation is rendered
    const actionPill = drawer.locator('.analyst-action-pill, .analyst-citation-chip').first();
    await expect(actionPill).toBeVisible();

    // 6. Close drawer
    const closeBtn = drawer.locator('button[title="Close Analyst Drawer"]');
    await closeBtn.click({ force: true });
    await expect(drawer).not.toBeVisible();
  });
});
