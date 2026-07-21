const billingTableBody = document.querySelector("#bill-items tbody");
const addRowButton = document.getElementById("add-row");
const paymentStatusSelect = document.getElementById("payment-status");
const paidAmountInput = document.getElementById("paid-amount");
const previousPendingInput = document.getElementById("previous-pending-amount");
const customerSelect = document.getElementById("customer-id");
const customerBalance = document.getElementById("customer-balance");

function formatCurrency(value) {
    return `Rs ${Number(value).toFixed(2)}`;
}

function getSelectedPrice(row) {
    const select = row.querySelector(".product-select");
    const option = select.options[select.selectedIndex];
    return Number(option?.dataset.price || 0);
}

function getQuantity(row) {
    const qtyInput = row.querySelector(".qty-input");
    return Number(qtyInput.value || 0);
}

function updateRow(row) {
    const price = getSelectedPrice(row);
    const qty = getQuantity(row);
    const lineTotal = price * qty;
    const priceCell = row.querySelector(".price-cell");
    const lineTotalCell = row.querySelector(".line-total-cell");

    priceCell.dataset.price = String(price);
    lineTotalCell.dataset.lineTotal = String(lineTotal);
    priceCell.textContent = formatCurrency(price);
    lineTotalCell.textContent = formatCurrency(lineTotal);
    updateSummary();
}

function updateSummary() {
    const rows = document.querySelectorAll(".bill-row");
    let subtotal = 0;

    rows.forEach((row) => {
        subtotal += Number(row.querySelector(".line-total-cell").dataset.lineTotal || 0);
    });

    const taxAmount = subtotal * ((window.billingConfig?.taxPercent || 0) / 100);
    const previousPending = Number(previousPendingInput?.value || 0);
    document.getElementById("subtotal").textContent = formatCurrency(subtotal);
    document.getElementById("tax-amount").textContent = formatCurrency(taxAmount);
    document.getElementById("previous-pending").textContent = formatCurrency(previousPending);
    document.getElementById("grand-total").textContent = formatCurrency(subtotal + taxAmount + previousPending);
    updatePaymentFields();
}

function currentGrandTotal() {
    const rows = document.querySelectorAll(".bill-row");
    let subtotal = 0;

    rows.forEach((row) => {
        subtotal += Number(row.querySelector(".line-total-cell").dataset.lineTotal || 0);
    });

    const previousPending = Number(previousPendingInput?.value || 0);
    return subtotal + subtotal * ((window.billingConfig?.taxPercent || 0) / 100) + previousPending;
}

function updatePaymentFields() {
    if (!paymentStatusSelect || !paidAmountInput) {
        return;
    }

    if (paymentStatusSelect.value === "Partial") {
        paidAmountInput.disabled = false;
        paidAmountInput.required = true;
        return;
    }

    paidAmountInput.required = false;
    paidAmountInput.disabled = true;
    paidAmountInput.value = paymentStatusSelect.value === "Paid" ? currentGrandTotal().toFixed(2) : "0.00";
}

function updateCustomerSelection() {
    if (!customerSelect || !previousPendingInput) {
        return;
    }

    const selectedCustomer = customerSelect.options[customerSelect.selectedIndex];
    const hasCustomer = Boolean(customerSelect.value);
    const balance = Number(selectedCustomer?.dataset.balance || 0);

    previousPendingInput.disabled = hasCustomer;
    if (hasCustomer) {
        previousPendingInput.value = "0.00";
    }
    if (customerBalance) {
        customerBalance.hidden = !hasCustomer;
        customerBalance.textContent = `Current pending balance: ${formatCurrency(balance)}`;
    }
    updateSummary();
}

function resetRow(row) {
    row.querySelector(".product-select").value = "";
    updateProductPicker(row);
    row.querySelector(".qty-input").value = "1";
    row.querySelector(".price-cell").dataset.price = "0";
    row.querySelector(".line-total-cell").dataset.lineTotal = "0";
    row.querySelector(".price-cell").textContent = formatCurrency(0);
    row.querySelector(".line-total-cell").textContent = formatCurrency(0);
}

function productOptionLabel(option) {
    return option.textContent.trim();
}

function closeProductPickers(except = null) {
    document.querySelectorAll(".product-picker").forEach((picker) => {
        if (picker === except) {
            return;
        }
        picker.querySelector(".product-picker-panel").hidden = true;
        picker.querySelector(".product-picker-trigger").setAttribute("aria-expanded", "false");
    });
}

function updateProductPicker(row) {
    const select = row.querySelector(".product-select");
    const trigger = row.querySelector(".product-picker-trigger");
    const option = select.options[select.selectedIndex];
    trigger.textContent = select.value ? productOptionLabel(option) : "Select product";
}

function renderProductResults(row, query = "") {
    const select = row.querySelector(".product-select");
    const results = row.querySelector(".product-picker-results");
    const normalizedQuery = query.trim().toLowerCase();
    const matchingOptions = Array.from(select.options).filter((option) => (
        option.value && productOptionLabel(option).toLowerCase().includes(normalizedQuery)
    ));

    results.replaceChildren();

    if (!matchingOptions.length) {
        const emptyMessage = document.createElement("p");
        emptyMessage.className = "product-picker-empty";
        emptyMessage.textContent = "No matching products found.";
        results.appendChild(emptyMessage);
        return;
    }

    matchingOptions.forEach((option) => {
        const result = document.createElement("button");
        result.type = "button";
        result.className = "product-picker-option";
        result.setAttribute("role", "option");
        result.setAttribute("aria-selected", String(option.value === select.value));
        result.textContent = productOptionLabel(option);
        result.addEventListener("click", () => {
            select.value = option.value;
            updateProductPicker(row);
            row.querySelector(".product-picker-panel").hidden = true;
            row.querySelector(".product-picker-trigger").setAttribute("aria-expanded", "false");
            select.dispatchEvent(new Event("change", { bubbles: true }));
        });
        results.appendChild(result);
    });
}

function bindProductPicker(row) {
    const picker = row.querySelector(".product-picker");
    const trigger = picker.querySelector(".product-picker-trigger");
    const panel = picker.querySelector(".product-picker-panel");
    const search = picker.querySelector(".product-picker-search");

    trigger.addEventListener("click", () => {
        const willOpen = panel.hidden;
        closeProductPickers(willOpen ? picker : null);
        panel.hidden = !willOpen;
        trigger.setAttribute("aria-expanded", String(willOpen));
        if (willOpen) {
            search.value = "";
            renderProductResults(row);
            search.focus();
        }
    });

    search.addEventListener("input", () => renderProductResults(row, search.value));
    search.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            panel.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
            trigger.focus();
        }
    });
}

function bindRow(row) {
    bindProductPicker(row);
    row.querySelector(".product-select").addEventListener("change", () => updateRow(row));
    row.querySelector(".qty-input").addEventListener("input", () => updateRow(row));
    row.querySelector(".qty-input").addEventListener("focus", (event) => event.target.select());
    row.querySelector(".remove-row").addEventListener("click", () => {
        if (document.querySelectorAll(".bill-row").length > 1) {
            row.remove();
            updateSummary();
        }
    });
}

addRowButton?.addEventListener("click", () => {
    const firstRow = document.querySelector(".bill-row");
    const clonedRow = firstRow.cloneNode(true);

    resetRow(clonedRow);
    billingTableBody.appendChild(clonedRow);
    bindRow(clonedRow);
    updateSummary();
});

document.querySelectorAll(".bill-row").forEach((row) => {
    row.querySelector(".price-cell").dataset.price = "0";
    row.querySelector(".line-total-cell").dataset.lineTotal = "0";
    bindRow(row);
    updateProductPicker(row);
    updateRow(row);
});

document.addEventListener("click", (event) => {
    if (!event.target.closest(".product-picker")) {
        closeProductPickers();
    }
});

paymentStatusSelect?.addEventListener("change", updatePaymentFields);
previousPendingInput?.addEventListener("input", updateSummary);
customerSelect?.addEventListener("change", updateCustomerSelection);
updateCustomerSelection();
updatePaymentFields();
