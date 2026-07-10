**Project Delivery Objective: West Africa News Collection / AI News Aggregation System / News H5 Website**

---

### 1. Collection Strategy

- **Tier 1 (covering major West African markets)**

| Country | Recommended Sites | Reason |
| ------- | ----------------- | ------ |
| 🇳🇬 Nigeria | Premium Times, Punch, Channels TV | Largest economy in West Africa; highest news volume |
| 🇬🇭 Ghana | GhanaWeb, MyJoyOnline, Graphic | Representative of the English‑speaking market |
| 🇸🇳 Senegal | Seneweb, Dakaractu | Representative of Francophone West Africa |
| 🇨🇮 Côte d’Ivoire | Abidjan.net, Koaci | Representative of the French‑speaking commercial market |

- **Tier 2**  
  🇧🇯 Benin  
  🇹🇬 Togo  
  🇬🇳 Guinea

- **Low‑frequency collection**  
  🇬🇼 Guinea‑Bissau  
  🇨🇻 Cabo Verde  
  🇱🇷 Liberia  
  🇸🇱 Sierra Leone

---

### 2. H5 Website Features

#### Homepage
- Top left: Logo; to the right of the Logo, the text “ZokoDaily”.  
  Top right: language switch button and search button.
- Next: a banner with 5 news images that automatically rotate in sequence. Each image corresponds to a news item; clicking it navigates to the corresponding news detail page.
- Next: the news list, displayed in two columns (two news items per row). Each item includes an image, headline, date, and country (with a flag icon). Clicking an item navigates to its detail page.
- Pull‑to‑refresh on the news list.

#### News Detail Page
- Top left: back button; to the right of the button, the news country & category.  
  Top right: share button, enabling sharing to Facebook, WhatsApp, WeChat, and other social media/communication tools.
- Next: the main news image and headline.  
  Top right of this section: language switch button. If the source is English, it shows “EN｜ZH｜BL”; if the source is French, it shows “FR｜ZH｜BL”. These represent: source language only, Chinese only, and bilingual (source + Chinese).
- Below the main image: the country, news category, and date.
- Next: the news headline in bold.
- Below the headline: the source website.
- Next: the news content, displayed in the source language by default.
- For the bilingual view: the content is split by the source’s natural paragraphs – each original paragraph is followed by its Chinese translation.

---

### 3. Admin Backend Features

- Manage the target countries and the target websites under each country for collection.
- Manage the daily collected news: view and edit.
- Automatically translate collected news into Chinese.
- Manage crawler status and the translation success/failure status for each news item.
- Manage the AI translation configuration: base URL, API key, and other related information.

---

For the web crawler, consider using advanced open‑source frameworks such as Scrapy, Crawl4AI, etc. Priority should be given to crawlers that are less likely to be blocked by the target websites.