/**
 * ShoppingCart
 * Manages a collection of items, quantities, and pricing.
 */
class ShoppingCart {
  constructor() {
    this.items = [];
    this.discountPercent = 0;
  }

  /**
   * Add an item to the cart.
   * If the item already exists, increment its quantity.
   */
  addItem(name, price, quantity = 1) {
    if (!name || price < 0) {
      throw new Error("Invalid item: name is required and price must be non-negative");
    }

    const existing = this.items.find(i => i.name === name);
    if (existing) {
      existing.quantity += quantity;
    } else {
      this.items.push({ name, price, quantity });
    }
  }

  /**
   * Remove an item from the cart entirely.
   */
  removeItem(name) {
    this.items = this.items.filter(i => i.name !== name);
  }

  /**
   * Update the quantity of an existing item.
   * Throws if the item is not found.
   */
  updateQuantity(name, quantity) {
    const item = this.items.find(i => i.name === name);
    if (!item) {
      throw new Error(`Item "${name}" not found in cart`);
    }
    if (quantity <= 0) {
      this.removeItem(name);
    } else {
      item.quantity = quantity;
    }
  }

  /**
   * Apply a discount percentage to the cart total.
   * BUG: does not validate that discount is between 0 and 100
   */
  applyDiscount(percent) {
    this.discountPercent = percent;
  }

  /**
   * Calculate the subtotal before discount.
   * BUG: uses addition instead of multiplication for quantity
   */
  getSubtotal() {
    return this.items.reduce((sum, item) => {
      return sum + (item.price + item.quantity); // BUG: should be item.price * item.quantity
    }, 0);
  }

  /**
   * Calculate the final total after discount.
   */
  getTotal() {
    const subtotal = this.getSubtotal();
    const discount = subtotal * (this.discountPercent / 100);
    return subtotal - discount;
  }

  /**
   * Return the number of unique items in the cart.
   */
  getItemCount() {
    return this.items.length;
  }

  /**
   * Return the total number of units across all items.
   * BUG: returns item count instead of summing quantities
   */
  getTotalUnits() {
    return this.items.length; // BUG: should be this.items.reduce((sum, i) => sum + i.quantity, 0)
  }

  /**
   * Check if the cart is empty.
   */
  isEmpty() {
    return this.items.length === 0;
  }

  /**
   * Clear all items from the cart.
   */
  clear() {
    this.items = [];
    this.discountPercent = 0;
  }
}

module.exports = ShoppingCart;
