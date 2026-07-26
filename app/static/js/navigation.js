const activeNavigationKey = "smartStoreActiveNavigation";
const activeSidebarKey = "smartStoreActiveSidebarItem";
const headerNavItems = document.querySelectorAll("[data-header-nav-item]");
const topNavItems = document.querySelectorAll("[data-top-nav-item]");
const sidebarItems = document.querySelectorAll("[data-sidebar-item]");

function clearHeaderNavItems() {
    headerNavItems.forEach((item) => {
        item.classList.remove("active");
        item.removeAttribute("aria-current");
    });
}

function clearTopNavItems() {
    topNavItems.forEach((item) => {
        item.classList.remove("active");
        item.removeAttribute("aria-current");
    });
}

function clearSidebarItems() {
    sidebarItems.forEach((item) => {
        item.classList.remove("active");
        item.setAttribute("aria-pressed", "false");
    });
}

function setActiveHeaderNavItem(activeItem) {
    headerNavItems.forEach((item) => {
        const isActive = item === activeItem;
        item.classList.toggle("active", isActive);
        if (isActive) {
            item.setAttribute("aria-current", "page");
        } else {
            item.removeAttribute("aria-current");
        }
    });
}

function setActiveTopNavItem(activeItem) {
    topNavItems.forEach((item) => {
        const isActive = item === activeItem;
        item.classList.toggle("active", isActive);
        if (isActive) {
            item.setAttribute("aria-current", "page");
        } else {
            item.removeAttribute("aria-current");
        }
    });
}

function setActiveSidebarItem(activeItem) {
    sidebarItems.forEach((item) => {
        const isActive = item === activeItem;
        item.classList.toggle("active", isActive);
        item.setAttribute("aria-pressed", String(isActive));
    });
}

function activateHeaderNavItem(item) {
    setActiveHeaderNavItem(item);
    clearTopNavItems();
    clearSidebarItems();
    localStorage.setItem(activeNavigationKey, "header");
    localStorage.removeItem(activeSidebarKey);
}

function activateSidebarItem(item) {
    clearHeaderNavItems();
    clearTopNavItems();
    setActiveSidebarItem(item);
    localStorage.setItem(activeNavigationKey, "sidebar");
    localStorage.setItem(activeSidebarKey, item.dataset.sidebarItem);
}

function activateTopNavItem(item) {
    clearHeaderNavItems();
    setActiveTopNavItem(item);
    clearSidebarItems();
    localStorage.setItem(activeNavigationKey, "top");
    localStorage.removeItem(activeSidebarKey);
}

if (localStorage.getItem(activeNavigationKey) === "header") {
    const activeHeaderItem = document.querySelector("[data-header-nav-item].active") || headerNavItems[0];
    clearTopNavItems();
    clearSidebarItems();
    if (activeHeaderItem) {
        setActiveHeaderNavItem(activeHeaderItem);
    }
} else if (localStorage.getItem(activeNavigationKey) === "sidebar") {
    const storedSidebarItem = localStorage.getItem(activeSidebarKey);
    const initialSidebarItem = storedSidebarItem
        ? document.querySelector(`[data-sidebar-item="${storedSidebarItem}"]`)
        : null;

    clearHeaderNavItems();
    clearTopNavItems();
    if (initialSidebarItem) {
        setActiveSidebarItem(initialSidebarItem);
    }
} else {
    clearHeaderNavItems();
    clearSidebarItems();
}

headerNavItems.forEach((item) => {
    item.addEventListener("click", () => activateHeaderNavItem(item));
});

topNavItems.forEach((item) => {
    item.addEventListener("click", () => activateTopNavItem(item));
});

sidebarItems.forEach((item) => {
    item.setAttribute("aria-pressed", String(item.classList.contains("active")));
    item.addEventListener("click", () => activateSidebarItem(item));
    item.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            activateSidebarItem(item);
        }
    });
});
