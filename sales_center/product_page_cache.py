"""Bounded session cache and searchable selectors for product analytics."""
from .product_analytics import price_list,price_types,category_paths,buyers
from .product_design_data import period_window,filter_sales,catalog_view,warehouse_options,export_catalog_csv


class ProductPageCache:
    """Bounded, per-session calculations for immutable source snapshots.

    Frame references prevent object-ID reuse from accepting an unrelated source.
    A replacement snapshot, source revision, or Moscow date invalidates the cache.
    Only the latest filter result and selected product are retained; this object
    must live in the user's session, never in a shared Streamlit cache.
    """

    def __init__(self, products, clients, lines, today, revision):
        self.frames = (products, clients, lines)
        self.today = today
        self.revision = revision
        self.types = price_types(products)
        self.buyer_names = clients.set_index('client_id').company.to_dict()
        self.warehouses = warehouse_options(lines)
        self._categories = None
        self._sales = None
        self._view = None
        self._buyers = None

    def matches(self, products, clients, lines, today, revision):
        return (all(previous is current for previous, current in
                    zip(self.frames, (products, clients, lines)))
                and self.today == today and self.revision == revision)

    def categories(self, price_type):
        if self._categories is None or self._categories[0] != price_type:
            self._categories = (price_type, [None] + category_paths(
                price_list(self.frames[0], price_type, positive=False)))
        return self._categories[1]

    def sales(self, period, buyer_id=None, warehouse_id=None):
        key = (period, buyer_id, warehouse_id)
        if self._sales is None or self._sales[0] != key:
            start, end = period_window(self.frames[2], self.today, period)
            sales = filter_sales(self.frames[2], start, end, buyer_id, warehouse_id)
            self._sales = (key, start, end, sales)
            self._view = None
            self._buyers = None
        return self._sales[1:]

    def catalog(self, price_type, category=None, query='', only_sales=False,
                sort='revenue', positive=True):
        if self._sales is None:
            raise ValueError('Сначала выберите период продаж.')
        key = (price_type, category, query, only_sales, sort, positive)
        if self._view is None or self._view[0] != key:
            view = catalog_view(self.frames[0], self._sales[3], price_type,
                                category, query, only_sales, sort, positive)
            self._view = (key, view, export_catalog_csv(view))
        return self._view[1:]

    def product_buyers(self, product_id):
        if self._sales is None:
            raise ValueError('Сначала выберите период продаж.')
        if self._buyers is None or self._buyers[0] != product_id:
            self._buyers = (product_id, buyers(
                self._sales[3], self.frames[1], product_id, self.today))
        return self._buyers[1]


def buyer_options(names, query='', selected=None, limit=200):
    """Bound dropdown payload while keeping every buyer reachable by search."""
    query = str(query or '').strip().casefold()
    matched = [cid for cid, name in names.items()
               if not query or query in str(name).casefold()]
    options = matched[:limit]
    if selected in names and selected not in options:
        options.append(selected)
    return [None] + options, len(matched)


