# polyforge-test-app

A simple Node.js shopping cart app used for testing the PolyForge pipeline.

## Structure

```
polyforge-test-app/
├── package.json
├── jest.config.json
├── src/
│   ├── index.js      # entry point
│   └── cart.js       # ShoppingCart class
└── tests/
    └── cart.test.js  # Jest test suite
```

## Run

```bash
npm install
npm test
npm start
```

## Intentional Bugs in cart.js

This app contains three deliberate bugs for PolyForge to find and fix:

1. **getSubtotal()** — uses `+` instead of `*` for quantity calculation
   - `item.price + item.quantity` should be `item.price * item.quantity`

2. **getTotalUnits()** — returns item count instead of summing quantities
   - `this.items.length` should be `this.items.reduce((sum, i) => sum + i.quantity, 0)`

3. **applyDiscount()** — no validation that discount is between 0 and 100
   - Should throw if percent < 0 or percent > 100

The test suite is written to catch all three bugs — running `npm test` against
the unmodified code will show failures. A correct fix should make all tests pass.
