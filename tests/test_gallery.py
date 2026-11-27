"""Offline HTML structure and fallback links stay compatible with manifests."""
from collections import Counter
from datetime import date
from html.parser import HTMLParser
import unittest

from calendar_models import CalendarPage
from gallery import render_gallery
from verify_release import PreviewLinks


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.pages = [CalendarPage(date(2027, 1, 1), 'A', 'A', '<script>alert(1)</script>', '出处 & 测试'),
                      CalendarPage(date(2028, 1, 1), 'B', 'B', '测试文字', '测试来源')]

    def test_year_months_are_distinct_and_content_is_escaped(self):
        document = render_gallery(self.pages, 17)
        tags = Tags(document).tags
        cards = [attrs for tag, attrs in tags if tag == 'article']
        self.assertEqual([card['data-month'] for card in cards], ['2027-01', '2028-01'])
        self.assertNotIn('<script>alert(1)</script>', document)
        self.assertIn('&lt;script&gt;', document)
        months = [attrs for tag, attrs in tags if tag == 'label' and attrs.get('for') == 'month']
        self.assertNotIn('hidden', months[0])
        single = Tags(render_gallery(self.pages[:1], None)).tags
        self.assertIn('hidden', next(attrs for tag, attrs in single if tag == 'label' and attrs.get('for') == 'month'))

    def test_original_links_and_lazy_images_survive_without_script(self):
        document = render_gallery(self.pages, None)
        parser = PreviewLinks()
        parser.feed(document)
        expected = Counter({('a', 'manifest.csv'): 1})
        for page in self.pages:
            name = f'{page.target_date.isoformat()}_layout-{page.layout}'
            expected['a', f'png/{name}.png'] += 2
            expected['a', f'svg/{name}.svg'] += 1
            expected['img', f'png/{name}.png'] += 1
        self.assertEqual(parser.links, expected)
        tags = Tags(document).tags
        self.assertTrue(all(attrs.get('loading') == 'lazy' for tag, attrs in tags if tag == 'img' and 'src' in attrs))
        self.assertTrue(any(tag == 'dialog' and attrs.get('aria-labelledby') == 'viewer-title' for tag, attrs in tags))
        self.assertNotIn('https://', document)
        self.assertFalse(any(tag in ('script', 'link') and ('src' in attrs or 'href' in attrs) for tag, attrs in tags))
