(function () {
    const salesOverviewCanvas = document.getElementById("salesOverviewChart");
    const topProductsCanvas = document.getElementById("topProductsChart");
    const salesFilterButtons = document.querySelectorAll("[data-sales-filter]");

    function animateCountUp() {
        const countUpElements = document.querySelectorAll("[data-countup]");
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        countUpElements.forEach((element) => {
            const targetValue = Number(element.dataset.countupValue || 0);
            const decimals = Number(element.dataset.countupDecimals || 0);
            const prefix = element.dataset.countupPrefix || "";
            const suffix = element.dataset.countupSuffix || "";
            const duration = reducedMotion ? 0 : 650;
            const startTime = performance.now();

            function formatValue(value) {
                return `${prefix}${value.toLocaleString("en-IN", {
                    minimumFractionDigits: decimals,
                    maximumFractionDigits: decimals
                })}${suffix}`;
            }

            function renderFrame(now) {
                const progress = duration === 0 ? 1 : Math.min((now - startTime) / duration, 1);
                const easedProgress = 1 - Math.pow(1 - progress, 3);
                element.textContent = formatValue(targetValue * easedProgress);

                if (progress < 1) {
                    requestAnimationFrame(renderFrame);
                }
            }

            requestAnimationFrame(renderFrame);
        });
    }

    animateCountUp();

    if (!window.Chart || !salesOverviewCanvas || !topProductsCanvas) {
        return;
    }

    const dashboardChartData = window.dashboardChartData || {};
    const salesOverviewData = dashboardChartData.salesOverview || { labels: [], values: [] };
    const topProductsData = dashboardChartData.topProducts || { labels: [], values: [] };
    const defaultEmptySalesMessage = "\u{1F4C8} No sales data available.\nCreate your first bill to start viewing analytics.";

    const chartColors = {
        blue: "#3B82F6",
        purple: "#8B5CF6",
        orange: "#F59E0B",
        gridLight: "rgba(100, 116, 139, 0.18)",
        gridDark: "rgba(203, 213, 225, 0.16)"
    };

    function getThemeColors() {
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        const styles = getComputedStyle(document.documentElement);

        return {
            text: styles.getPropertyValue("--brand-text").trim(),
            muted: styles.getPropertyValue("--brand-muted").trim(),
            grid: isDark ? chartColors.gridDark : chartColors.gridLight
        };
    }

    function applyScaleTheme(chart) {
        const themeColors = getThemeColors();

        chart.options.plugins.legend.labels.color = themeColors.muted;

        Object.values(chart.options.scales).forEach((scale) => {
            scale.ticks.color = themeColors.muted;
            scale.grid.color = themeColors.grid;
            scale.border.color = themeColors.grid;
        });

        chart.update();
    }

    function hasChartData(chartData) {
        return Array.isArray(chartData.values) && chartData.values.some((value) => Number(value) > 0);
    }

    function parseDateOnly(value) {
        const parts = String(value || "").split("-").map((part) => Number(part));

        if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) {
            return null;
        }

        return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function toDateKey(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    function addDays(date, amount) {
        const nextDate = new Date(date);
        nextDate.setDate(nextDate.getDate() + amount);
        return nextDate;
    }

    function formatDayLabel(date) {
        return date.toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short"
        });
    }

    function formatHourLabel(value) {
        if (typeof value === "number") {
            return `${String(value).padStart(2, "0")}:00`;
        }

        return String(value || "");
    }

    function getCurrentDate() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return today;
    }

    function getSalesTotalByDate() {
        return salesSeries.reduce((totals, entry) => {
            totals.set(entry.key, (totals.get(entry.key) || 0) + entry.value);
            return totals;
        }, new Map());
    }

    function getDailySales(days) {
        const totalsByDate = getSalesTotalByDate();
        const endDate = getCurrentDate();
        const startDate = addDays(endDate, -(days - 1));
        const labels = [];
        const values = [];

        for (let index = 0; index < days; index += 1) {
            const date = addDays(startDate, index);
            const key = toDateKey(date);
            labels.push(formatDayLabel(date));
            values.push(totalsByDate.get(key) || 0);
        }

        return {
            labels,
            values,
            emptyMessage: defaultEmptySalesMessage
        };
    }

    function getTodaySales() {
        const hourlyData = salesOverviewData.todayHourly || salesOverviewData.hourly;

        if (hourlyData && Array.isArray(hourlyData.labels) && Array.isArray(hourlyData.values)) {
            return {
                labels: hourlyData.labels.map(formatHourLabel),
                values: hourlyData.values.map((value) => Number(value) || 0),
                emptyMessage: defaultEmptySalesMessage
            };
        }

        const totalsByDate = getSalesTotalByDate();
        const today = getCurrentDate();
        const todayTotal = totalsByDate.get(toDateKey(today)) || 0;

        return {
            labels: todayTotal > 0 ? ["Today"] : [],
            values: todayTotal > 0 ? [todayTotal] : [],
            emptyMessage: defaultEmptySalesMessage
        };
    }

    function getYearlySales() {
        const monthLabels = Array.from({ length: 12 }, (_, index) => (
            new Date(2000, index, 1).toLocaleDateString("en-IN", { month: "short" })
        ));
        const values = Array(12).fill(0);
        const currentYear = getCurrentDate().getFullYear();

        salesSeries.forEach((entry) => {
            if (entry.date && entry.date.getFullYear() === currentYear) {
                values[entry.date.getMonth()] += entry.value;
            }
        });

        return {
            labels: monthLabels,
            values,
            emptyMessage: defaultEmptySalesMessage
        };
    }

    function getSalesDataForFilter(filterName) {
        if (filterName === "today") {
            return getTodaySales();
        }

        if (filterName === "30days") {
            return getDailySales(30);
        }

        if (filterName === "year") {
            return getYearlySales();
        }

        return getDailySales(7);
    }

    function truncateProductLabel(label) {
        const text = String(label || "");

        if (text.length <= 18) {
            return text;
        }

        return `${text.slice(0, 15).trim()}...`;
    }

    function setActiveFilter(activeButton) {
        salesFilterButtons.forEach((button) => {
            const isActive = button === activeButton;
            button.classList.toggle("btn-primary", isActive);
            button.classList.toggle("btn-outline-primary", !isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
    }

    function updateSalesOverview(filterName) {
        const filteredData = getSalesDataForFilter(filterName);
        salesOverviewChart.data.labels = hasChartData(filteredData) ? filteredData.labels : [];
        salesOverviewChart.data.datasets[0].data = hasChartData(filteredData) ? filteredData.values : [];
        salesOverviewChart.options.plugins.emptyChartMessage.text = hasChartData(filteredData)
            ? ""
            : filteredData.emptyMessage;
        salesOverviewChart.update();
    }

    const emptyChartMessagePlugin = {
        id: "emptyChartMessage",
        afterDraw(chart) {
            const message = chart.options.plugins.emptyChartMessage?.text;

            if (!message) {
                return;
            }

            const { ctx, chartArea } = chart;
            const themeColors = getThemeColors();
            const centerX = (chartArea.left + chartArea.right) / 2;
            const centerY = (chartArea.top + chartArea.bottom) / 2;
            const lines = message.split("\n");

            ctx.save();
            ctx.fillStyle = themeColors.muted;
            ctx.font = "600 14px system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            lines.forEach((line, index) => {
                ctx.fillText(line, centerX, centerY + (index - (lines.length - 1) / 2) * 22);
            });
            ctx.restore();
        }
    };

    Chart.register(emptyChartMessagePlugin);

    const salesSeries = (salesOverviewData.labels || []).map((label, index) => {
        const date = parseDateOnly(label);
        const value = Number((salesOverviewData.values || [])[index]) || 0;

        return {
            key: date ? toDateKey(date) : String(label || ""),
            date,
            value
        };
    }).filter((entry) => entry.date);

    const initialSalesData = getSalesDataForFilter("7days");
    const topProductLabels = topProductsData.labels || [];

    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    boxWidth: 12,
                    color: getThemeColors().muted,
                    font: {
                        weight: "600"
                    }
                }
            },
            tooltip: {
                backgroundColor: "rgba(17, 24, 39, 0.92)",
                padding: 12,
                titleFont: {
                    weight: "700"
                },
                bodyFont: {
                    weight: "600"
                }
            },
            emptyChartMessage: {
                text: ""
            }
        },
        animation: {
            duration: 450,
            easing: "easeOutQuart"
        },
        transitions: {
            active: {
                animation: {
                    duration: 220
                }
            }
        },
        scales: {
            x: {
                ticks: {
                    color: getThemeColors().muted,
                    autoSkip: true,
                    maxRotation: 0,
                    maxTicksLimit: 8,
                    font: {
                        weight: "600"
                    }
                },
                grid: {
                    color: getThemeColors().grid
                },
                border: {
                    color: getThemeColors().grid
                }
            },
            y: {
                beginAtZero: true,
                ticks: {
                    color: getThemeColors().muted,
                    font: {
                        weight: "600"
                    }
                },
                grid: {
                    color: getThemeColors().grid
                },
                border: {
                    color: getThemeColors().grid
                }
            }
        }
    };

    const salesOverviewChart = new Chart(salesOverviewCanvas, {
        type: "line",
        data: {
            labels: hasChartData(initialSalesData) ? initialSalesData.labels : [],
            datasets: [
                {
                    label: "Sales",
                    data: hasChartData(initialSalesData) ? initialSalesData.values : [],
                    borderColor: chartColors.blue,
                    backgroundColor: "rgba(59, 130, 246, 0.12)",
                    borderWidth: 3,
                    pointBackgroundColor: chartColors.blue,
                    pointBorderColor: "#FFFFFF",
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.35,
                    fill: true
                }
            ]
        },
        options: {
            ...baseOptions,
            plugins: {
                ...baseOptions.plugins,
                emptyChartMessage: {
                    text: hasChartData(initialSalesData) ? "" : initialSalesData.emptyMessage
                }
            }
        }
    });

    const topProductsChart = new Chart(topProductsCanvas, {
        type: "bar",
        data: {
            labels: topProductLabels.map(truncateProductLabel),
            datasets: [
                {
                    label: "Units Sold",
                    data: topProductsData.values,
                    backgroundColor: chartColors.purple,
                    borderColor: chartColors.purple,
                    borderRadius: 6,
                    maxBarThickness: 42
                }
            ]
        },
        options: {
            ...baseOptions,
            plugins: {
                ...baseOptions.plugins,
                legend: {
                    display: false,
                    labels: baseOptions.plugins.legend.labels
                },
                tooltip: {
                    ...baseOptions.plugins.tooltip,
                    callbacks: {
                        title(items) {
                            const item = items[0];
                            return topProductLabels[item.dataIndex] || item.label;
                        }
                    }
                },
                emptyChartMessage: {
                    text: hasChartData(topProductsData) ? "" : topProductsData.emptyMessage
                }
            }
        }
    });

    salesFilterButtons.forEach((button) => {
        button.addEventListener("click", () => {
            setActiveFilter(button);
            updateSalesOverview(button.dataset.salesFilter);
        });
    });

    const themeObserver = new MutationObserver(() => {
        applyScaleTheme(salesOverviewChart);
        applyScaleTheme(topProductsChart);
    });

    themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"]
    });
})();
