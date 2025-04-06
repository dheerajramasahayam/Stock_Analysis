document.addEventListener('DOMContentLoaded', () => {
    const stockListDiv = document.getElementById('stock-list');
    const sectorFilter = document.getElementById('sector-filter');
    const sortBy = document.getElementById('sort-by');
    const applyFiltersButton = document.getElementById('apply-filters');
    const stockDetailsSection = document.getElementById('stock-details');
    const detailsContent = document.getElementById('details-content');
    const detailsTickerSpan = document.getElementById('details-ticker');
    const detailsNameH3 = document.getElementById('details-name');
    const detailsSectorSpan = document.getElementById('details-sector');
    // const detailsNewsList = document.getElementById('details-news-list'); // No longer needed
    const detailsGeminiSummaryP = document.getElementById('details-gemini-summary'); // New element
    const closeDetailsButton = document.getElementById('close-details');
    const priceChartCanvas = document.getElementById('price-chart');

    let priceChart = null; // To hold the Chart.js instance
    let allStocksData = []; // To store fetched data for client-side filtering/sorting

    // --- Fetch and Display Stocks ---
    async function fetchAndDisplayStocks() {
        stockListDiv.innerHTML = '<p>Loading stocks...</p>'; // Show loading state
        try {
            const response = await fetch('/api/highlighted-stocks');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            allStocksData = await response.json();
            renderStockList(); // Initial render with default sorting
        } catch (error) {
            console.error('Error fetching stocks:', error);
            stockListDiv.innerHTML = '<p>Error loading stocks. Please try again later.</p>';
        }
    }

    // --- Render Stock List ---
    function renderStockList() {
        stockListDiv.innerHTML = ''; // Clear previous list

        let filteredStocks = [...allStocksData]; // Copy data

        // Apply Sector Filter
        const selectedSector = sectorFilter.value;
        if (selectedSector !== 'all') {
            filteredStocks = filteredStocks.filter(stock => stock.sector === selectedSector);
        }

        // Apply Sorting
        const sortValue = sortBy.value;
        filteredStocks.sort((a, b) => {
            switch (sortValue) {
                case 'score_asc': return (a.score ?? 0) - (b.score ?? 0);
                case 'price_change_desc': return (b.price_change ?? -Infinity) - (a.price_change ?? -Infinity);
                case 'price_change_asc': return (a.price_change ?? Infinity) - (b.price_change ?? Infinity);
                case 'sentiment_desc': return (b.avg_sentiment ?? -Infinity) - (a.avg_sentiment ?? -Infinity);
                case 'sentiment_asc': return (a.avg_sentiment ?? Infinity) - (b.avg_sentiment ?? Infinity);
                case 'score_desc': // Default
                default:
                    return (b.score ?? 0) - (a.score ?? 0);
            }
        });

        if (filteredStocks.length === 0) {
            stockListDiv.innerHTML = '<p>No stocks match the current filters.</p>';
            return;
        }

        // Create and append stock cards
        filteredStocks.forEach(stock => {
            const card = document.createElement('div');
            card.classList.add('stock-card');
            card.dataset.ticker = stock.ticker; // Store ticker for click handling

            card.innerHTML = `
                <h3>${stock.ticker} - ${stock.name || 'N/A'}</h3>
                <p><span class="label">Sector:</span> ${stock.sector || 'N/A'}</p>
                <p><span class="label">Score:</span> ${stock.score?.toFixed(2) ?? 'N/A'}</p>
                <p><span class="label">Price Change (5d %):</span> ${stock.price_change_pct?.toFixed(2) ?? 'N/A'}</p>
                <p><span class="label">Volume Ratio:</span> ${stock.volume_ratio?.toFixed(2) ?? 'N/A'}</p>
                <p><span class="label">P/E Ratio:</span> ${stock.pe_ratio?.toFixed(2) ?? 'N/A'}</p>
                <p><span class="label">Dividend Yield %:</span> ${stock.dividend_yield ? (stock.dividend_yield * 100).toFixed(2) : 'N/A'}</p>
                <p><span class="label">Sentiment Score:</span> ${stock.avg_sentiment?.toFixed(2) ?? 'N/A'}</p>
                <p><span class="label">Price vs MA(50):</span> ${stock.price_vs_ma50 ?? 'N/A'}</p>
                <p><span class="label">RSI(14):</span> ${stock.rsi?.toFixed(2) ?? 'N/A'}</p>
            `;
            card.addEventListener('click', () => showStockDetails(stock.ticker));
            stockListDiv.appendChild(card);
        });
    }

    // --- Show Stock Details ---
    async function showStockDetails(ticker) {
        try {
            const response = await fetch(`/api/stock-details/${ticker}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const details = await response.json();

            // Populate details section
            detailsTickerSpan.textContent = details.ticker;
            detailsNameH3.textContent = details.name || `${details.ticker} Details`;
            detailsSectorSpan.textContent = details.sector || 'N/A';

            // Display Gemini Summary and Points
            detailsGeminiSummaryP.textContent = details.gemini_summary || 'No analysis summary available.';
            renderAnalysisPoints('details-bullish-points', details.bullish_points || []);
            renderAnalysisPoints('details-bearish-points', details.bearish_points || []);

            // Render chart
            renderPriceChart(details.price_history || []);

            // Show details section
            stockDetailsSection.classList.remove('hidden');
            stockDetailsSection.scrollIntoView({ behavior: 'smooth' });

        } catch (error) {
            console.error(`Error fetching details for ${ticker}:`, error);
            alert(`Could not load details for ${ticker}.`);
        }
    }

    // --- Render Price Chart ---
    function renderPriceChart(priceHistory) {
        const ctx = priceChartCanvas.getContext('2d');

        if (priceChart) {
            priceChart.destroy(); // Destroy previous chart instance
        }

        const labels = priceHistory.map(p => p.date);
        const data = priceHistory.map(p => p.price);

        priceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Close Price',
                    data: data,
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day',
                            tooltipFormat: 'PP' // Format like 'Sep 4, 2019'
                        },
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Price'
                        }
                    }
                }
            }
        });
    }

    // --- Hide Stock Details ---
    function hideStockDetails() {
        stockDetailsSection.classList.add('hidden');
        if (priceChart) {
            priceChart.destroy(); // Clean up chart
            priceChart = null;
        }
    }

    // --- Event Listeners ---
    // --- Render Bullish/Bearish Points ---
    function renderAnalysisPoints(elementId, points) {
        const listElement = document.getElementById(elementId);
        listElement.innerHTML = ''; // Clear previous points
        if (points.length === 0) {
            listElement.innerHTML = '<li>None identified in recent results.</li>';
        } else {
            points.forEach(point => {
                const li = document.createElement('li');
                li.textContent = point;
                listElement.appendChild(li);
            });
        }
    }

    // --- Event Listeners ---
    applyFiltersButton.addEventListener('click', renderStockList);
    closeDetailsButton.addEventListener('click', hideStockDetails);

    const portfolioForm = document.getElementById('portfolio-form');
    const portfolioTableBody = document.getElementById('portfolio-table-body');
    const portfolioMessage = document.getElementById('portfolio-message');

    // --- Fetch and Display Portfolio ---
    async function fetchAndDisplayPortfolio() {
        portfolioTableBody.innerHTML = '<tr><td colspan="9">Loading portfolio...</td></tr>';
        try {
            const response = await fetch('/api/portfolio');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const portfolioData = await response.json();
            renderPortfolioTable(portfolioData);
        } catch (error) {
            console.error('Error fetching portfolio:', error);
            portfolioTableBody.innerHTML = '<tr><td colspan="9">Error loading portfolio.</td></tr>';
        }
    }

    // --- Render Portfolio Table ---
    function renderPortfolioTable(portfolioData) {
        portfolioTableBody.innerHTML = ''; // Clear previous data

        if (!portfolioData || portfolioData.length === 0) {
            portfolioTableBody.innerHTML = '<tr><td colspan="9">No holdings in portfolio.</td></tr>';
            return;
        }

        portfolioData.forEach(holding => {
            const row = document.createElement('tr');
            const currentPrice = holding.latest_price;
            const purchasePrice = holding.purchase_price;
            let gainLossPct = 'N/A';
            let gainLossClass = '';

            if (currentPrice && purchasePrice && purchasePrice > 0) {
                const pct = ((currentPrice - purchasePrice) / purchasePrice) * 100;
                gainLossPct = pct.toFixed(2) + '%';
                gainLossClass = pct >= 0 ? 'positive' : 'negative';
            }

            row.innerHTML = `
                <td>${holding.ticker}</td>
                <td>${holding.name || 'N/A'}</td>
                <td>${holding.quantity}</td>
                <td>$${holding.purchase_price?.toFixed(2) ?? 'N/A'}</td>
                <td>${holding.purchase_date}</td>
                <td>$${currentPrice?.toFixed(2) ?? 'N/A'}</td>
                <td class="${gainLossClass}">${gainLossPct}</td>
                <td>${holding.latest_score?.toFixed(2) ?? 'N/A'}</td>
                <td>
                    ${(holding.latest_score !== null && holding.latest_score < -1) ? '<span class="sell-suggestion">Consider Sell</span>' : ''}
                    <button class="delete-holding" data-id="${holding.id}">Delete</button>
                </td>
            `;
            portfolioTableBody.appendChild(row);
        });
    }

     // --- Handle Add Holding Form Submission ---
     portfolioForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission
        portfolioMessage.textContent = ''; // Clear previous messages
        portfolioMessage.className = 'message'; // Reset class

        const formData = new FormData(portfolioForm);
        const data = Object.fromEntries(formData.entries());

        // Basic frontend validation (match backend)
        if (!data.ticker || !data.quantity || !data.purchase_price || !data.purchase_date) {
            portfolioMessage.textContent = 'Error: All fields are required.';
            portfolioMessage.classList.add('error');
            return;
        }
         if (parseInt(data.quantity) <= 0 || parseFloat(data.purchase_price) <= 0) {
             portfolioMessage.textContent = 'Error: Quantity and Price must be positive.';
             portfolioMessage.classList.add('error');
             return;
         }

        try {
            const response = await fetch('/api/portfolio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `HTTP error! status: ${response.status}`);
            }

            portfolioMessage.textContent = result.message || 'Holding added successfully!';
            portfolioMessage.classList.add('success');
            portfolioForm.reset(); // Clear the form
            fetchAndDisplayPortfolio(); // Refresh the portfolio list

        } catch (error) {
            console.error('Error adding holding:', error);
            portfolioMessage.textContent = `Error: ${error.message}`;
            portfolioMessage.classList.add('error');
        }
    });

    // --- Handle Delete Holding ---
     portfolioTableBody.addEventListener('click', async (event) => {
         if (event.target.classList.contains('delete-holding')) {
             const holdingId = event.target.dataset.id;
             const row = event.target.closest('tr'); // Get the table row
             const ticker = row.cells[0].textContent; // Get ticker from the row for confirmation message

             if (confirm(`Are you sure you want to delete the holding for ${ticker} (ID: ${holdingId})?`)) {
                 portfolioMessage.textContent = ''; // Clear previous messages
                 portfolioMessage.className = 'message';
                 try {
                     const response = await fetch(`/api/portfolio/${holdingId}`, {
                         method: 'DELETE',
                     });
                     const result = await response.json();

                     if (!response.ok) {
                         throw new Error(result.error || `HTTP error! status: ${response.status}`);
                     }

                     portfolioMessage.textContent = result.message || 'Holding deleted successfully!';
                     portfolioMessage.classList.add('success');
                     fetchAndDisplayPortfolio(); // Refresh the portfolio list

                 } catch (error) {
                     console.error('Error deleting holding:', error);
                     portfolioMessage.textContent = `Error: ${error.message}`;
                     portfolioMessage.classList.add('error');
                 }
             }
         }
     });


    // --- Initial Load ---
    fetchAndDisplayStocks();
    fetchAndDisplayPortfolio(); // Fetch portfolio on load
});
