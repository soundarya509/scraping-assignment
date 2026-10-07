"""HTML fixtures shaped like the real sites + a fake HTTP client (no network in tests)."""
from bs4 import BeautifulSoup

BOOKS = "https://books.toscrape.com/"
QUOTES = "https://quotes.toscrape.com/"


def book_card(title, href, price="£51.77", rating="Three", avail="In stock"):
    return f"""<li class="col-xs-6"><article class="product_pod">
      <p class="star-rating {rating}"></p>
      <h3><a href="{href}" title="{title}">{title[:15]}...</a></h3>
      <div class="product_price"><p class="price_color">{price}</p>
      <p class="instock availability"> {avail} </p></div></article></li>"""


def books_page(cards, next_href=None):
    nxt = f'<li class="next"><a href="{next_href}">next</a></li>' if next_href else ""
    return f"<html><body><ol class='row'>{''.join(cards)}</ol><ul class='pager'>{nxt}</ul></body></html>"


def book_detail(category="Poetry", desc="A nice book."):
    d = f'<div id="product_description" class="sub-header"><h2>Product Description</h2></div><p>{desc}</p>' if desc else ""
    return f"""<html><body><ul class="breadcrumb"><li><a href="/">Home</a></li>
      <li><a href="/catalogue/category/books_1/index.html">Books</a></li>
      <li><a href="/x.html">{category}</a></li><li class="active">Title</li></ul>{d}</body></html>"""


def quote_card(text, author, tags, author_href="/author/Some-Author"):
    tag_html = "".join(f'<a class="tag" href="/tag/{t}/">{t}</a>' for t in tags)
    return f"""<div class="quote"><span class="text">“{text}”</span>
      <span>by <small class="author">{author}</small><a href="{author_href}">(about)</a></span>
      <div class="tags">Tags: {tag_html}</div></div>"""


def quotes_page(cards, next_href=None):
    nxt = f'<li class="next"><a href="{next_href}">Next</a></li>' if next_href else ""
    return f"<html><body>{''.join(cards)}<ul class='pager'>{nxt}</ul></body></html>"


def author_page(bio="Born in a small town."):
    return f'<html><body><div class="author-description">\n  {bio}  </div></body></html>'


class FakeClient:
    """Maps URL -> HTML (or None for a failed fetch). Unknown URLs behave like a 404."""
    def __init__(self, pages):
        self.pages, self.requested = pages, []

    def get_soup(self, url):
        self.requested.append(url)
        html = self.pages.get(url)
        return BeautifulSoup(html, "html.parser") if html else None
