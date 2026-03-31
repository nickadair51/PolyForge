const ShoppingCart = require('./cart');

describe('ShoppingCart', () => {

  let cart;

  beforeEach(() => {
    cart = new ShoppingCart();
  });

  // ── addItem ────────────────────────────────────────────────────────────────

  describe('addItem', () => {
    test('adds a new item to the cart', () => {
      cart.addItem('Apple', 1.50, 2);
      expect(cart.getItemCount()).toBe(1);
    });

    test('increments quantity if item already exists', () => {
      cart.addItem('Apple', 1.50, 2);
      cart.addItem('Apple', 1.50, 3);
      expect(cart.items[0].quantity).toBe(5);
    });

    test('defaults quantity to 1 when not specified', () => {
      cart.addItem('Apple', 1.50);
      expect(cart.items[0].quantity).toBe(1);
    });

    test('throws if name is empty', () => {
      expect(() => cart.addItem('', 1.50)).toThrow('Invalid item');
    });

    test('throws if price is negative', () => {
      expect(() => cart.addItem('Apple', -1)).toThrow('Invalid item');
    });

    test('allows price of zero', () => {
      expect(() => cart.addItem('Freebie', 0)).not.toThrow();
    });
  });

  // ── removeItem ─────────────────────────────────────────────────────────────

  describe('removeItem', () => {
    test('removes an existing item', () => {
      cart.addItem('Apple', 1.50);
      cart.removeItem('Apple');
      expect(cart.isEmpty()).toBe(true);
    });

    test('does nothing if item does not exist', () => {
      cart.addItem('Apple', 1.50);
      cart.removeItem('Banana');
      expect(cart.getItemCount()).toBe(1);
    });
  });

  // ── updateQuantity ─────────────────────────────────────────────────────────

  describe('updateQuantity', () => {
    test('updates the quantity of an existing item', () => {
      cart.addItem('Apple', 1.50, 2);
      cart.updateQuantity('Apple', 5);
      expect(cart.items[0].quantity).toBe(5);
    });

    test('removes item if quantity is set to zero', () => {
      cart.addItem('Apple', 1.50, 2);
      cart.updateQuantity('Apple', 0);
      expect(cart.isEmpty()).toBe(true);
    });

    test('removes item if quantity is negative', () => {
      cart.addItem('Apple', 1.50, 2);
      cart.updateQuantity('Apple', -1);
      expect(cart.isEmpty()).toBe(true);
    });

    test('throws if item not found', () => {
      expect(() => cart.updateQuantity('Ghost', 1)).toThrow('not found in cart');
    });
  });

  // ── applyDiscount ──────────────────────────────────────────────────────────

  describe('applyDiscount', () => {
    test('applies a valid discount percentage', () => {
      cart.addItem('Apple', 10.00, 1);
      cart.applyDiscount(10);
      expect(cart.getTotal()).toBeCloseTo(9.00);
    });

    test('rejects discount over 100 percent', () => {
      // This test exposes the missing validation bug
      expect(() => cart.applyDiscount(150)).toThrow();
    });

    test('rejects negative discount', () => {
      expect(() => cart.applyDiscount(-10)).toThrow();
    });
  });

  // ── getSubtotal ────────────────────────────────────────────────────────────

  describe('getSubtotal', () => {
    test('calculates subtotal correctly for single item', () => {
      cart.addItem('Apple', 2.00, 3);
      // 2.00 * 3 = 6.00
      expect(cart.getSubtotal()).toBeCloseTo(6.00);
    });

    test('calculates subtotal correctly for multiple items', () => {
      cart.addItem('Apple', 2.00, 3);   // 6.00
      cart.addItem('Bread', 3.00, 2);   // 6.00
      expect(cart.getSubtotal()).toBeCloseTo(12.00);
    });

    test('returns zero for empty cart', () => {
      expect(cart.getSubtotal()).toBe(0);
    });
  });

  // ── getTotal ───────────────────────────────────────────────────────────────

  describe('getTotal', () => {
    test('returns subtotal when no discount applied', () => {
      cart.addItem('Apple', 5.00, 2);  // 10.00
      expect(cart.getTotal()).toBeCloseTo(10.00);
    });

    test('applies discount correctly', () => {
      cart.addItem('Apple', 10.00, 2); // 20.00
      cart.applyDiscount(25);
      expect(cart.getTotal()).toBeCloseTo(15.00);
    });
  });

  // ── getTotalUnits ──────────────────────────────────────────────────────────

  describe('getTotalUnits', () => {
    test('returns sum of all item quantities', () => {
      cart.addItem('Apple', 1.50, 4);
      cart.addItem('Bread', 2.99, 2);
      cart.addItem('Milk',  3.49, 1);
      // 4 + 2 + 1 = 7
      expect(cart.getTotalUnits()).toBe(7);
    });

    test('returns zero for empty cart', () => {
      expect(cart.getTotalUnits()).toBe(0);
    });
  });

  // ── isEmpty / clear ────────────────────────────────────────────────────────

  describe('isEmpty', () => {
    test('returns true for new cart', () => {
      expect(cart.isEmpty()).toBe(true);
    });

    test('returns false after adding an item', () => {
      cart.addItem('Apple', 1.50);
      expect(cart.isEmpty()).toBe(false);
    });
  });

  describe('clear', () => {
    test('removes all items and resets discount', () => {
      cart.addItem('Apple', 1.50, 3);
      cart.applyDiscount(20);
      cart.clear();
      expect(cart.isEmpty()).toBe(true);
      expect(cart.discountPercent).toBe(0);
    });
  });

});
