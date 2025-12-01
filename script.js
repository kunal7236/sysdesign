// --- Setup ---
const POSTS_DATES_FILE = "posts_dates.json";
const POSTS_PER_PAGE = 5;
let allPosts = [];
let currentPage = 1;

const loadingIndicator = document.getElementById("loading-indicator");
const postsContainer = document.getElementById("posts-container");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const pageInfo = document.getElementById("page-info");
const pageInput = document.getElementById("page-input");
const goBtn = document.getElementById("go-btn");
const errorMessage = document.getElementById("error-message");

/**
 * Converts a URL path fragment (e.g., "how-to-do-x-y") into a human-readable title.
 * @param {string} url - The full URL.
 * @returns {string} - Cleaned-up title string.
 */
function deriveTitle(url) {
  try {
    // 1. Get the path part after the domain
    const urlObj = new URL(url);
    // Get the last non-empty path segment (e.g., from /blog/post-title/ -> "post-title")
    const pathSegments = urlObj.pathname
      .split("/")
      .filter((s) => s.length > 0);
    const slug = pathSegments[pathSegments.length - 1] || "";

    if (!slug) return "Untitled Blog Post";

    // 2. Remove file extensions and replace hyphens with spaces
    let title = slug
      .replace(/\.(html|php|aspx|p)$/i, "")
      .replace(/-/g, " ");

    // 3. Capitalize the first letter of each word (simple title case)
    title = title
      .toLowerCase()
      .split(" ")
      .map((word) => {
        if (word.length > 0) {
          return word.charAt(0).toUpperCase() + word.slice(1);
        }
        return word;
      })
      .join(" ");

    return title || "Untitled Blog Post";
  } catch (e) {
    return "Untitled Blog Post";
  }
}

/**
 * Derives a news-style summary from the URL slug.
 * @param {string} url - The full URL.
 * @returns {string} - A short summary snippet.
 */
function deriveSummary(url) {
  try {
    const urlObj = new URL(url);
    const pathSegments = urlObj.pathname
      .split("/")
      .filter((s) => s.length > 0);
    const slug = pathSegments[pathSegments.length - 1] || "";

    if (!slug)
      return "Breaking: New tech insights revealed. Click to read more.";

    // Get the first 5-8 words of the title for a short snippet
    let summaryWords = slug.replace(/-/g, " ").split(" ").slice(0, 8);

    // Capitalize first letter of the summary for news style
    if (summaryWords.length > 0) {
      summaryWords[0] =
        summaryWords[0].charAt(0).toUpperCase() +
        summaryWords[0].slice(1);
    }

    return summaryWords.join(" ") + "...";
  } catch (e) {
    return "Latest development in tech. Click to learn more.";
  }
}

/**
 * Loads posts with publish dates from the JSON file.
 * @returns {Promise<Array<{url: string, publishDate: string, title: string, summary: string}>>}
 */
async function loadPostsFromJSON() {
  try {
    errorMessage.style.display = "none";
    console.log(`Loading posts from ${POSTS_DATES_FILE}...`);

    const response = await fetch(POSTS_DATES_FILE);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const postsData = await response.json();

    // Enrich with title and summary
    const posts = postsData.map((post) => ({
      url: post.url,
      publishDate: post.publishDate || new Date().toISOString(),
      title: deriveTitle(post.url),
      summary: deriveSummary(post.url),
    }));

    console.log(`Successfully loaded ${posts.length} posts.`);
    return posts;
  } catch (error) {
    console.error("Error loading posts:", error.message);
    errorMessage.textContent = `Error loading posts: ${error.message}. Make sure to run the Python scraper first!`;
    errorMessage.style.display = "block";
    return [];
  }
}

/**
 * Renders the current page of posts to the DOM.
 */
function renderPosts() {
  postsContainer.innerHTML = "";
  const startIndex = (currentPage - 1) * POSTS_PER_PAGE;
  const endIndex = startIndex + POSTS_PER_PAGE;
  const postsToDisplay = allPosts.slice(startIndex, endIndex);

  if (postsToDisplay.length === 0) {
    postsContainer.innerHTML = '<li style="text-align: center; color: #999;">No posts to display.</li>';
    pageInfo.textContent = "Page 0 of 0";
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    return;
  }

  postsToDisplay.forEach((post) => {
    const li = document.createElement("li");
    li.className = "post-item";

    const displayDate = post.publishDate || post.lastmod;
    const formattedDate = new Date(displayDate).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });

    li.innerHTML = `
      <a href="${post.url}" target="_blank" class="post-link">
        <span class="post-title">${post.title}</span>
        <span class="post-date">${formattedDate}</span>
      </a>
    `;
    
    postsContainer.appendChild(li);
  });

  // Update pagination controls
  const totalPages = Math.ceil(allPosts.length / POSTS_PER_PAGE);
  pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
  prevBtn.disabled = currentPage === 1;
  nextBtn.disabled = currentPage === totalPages;
  pageInput.max = totalPages;
}

/**
 * Handles navigation for the blog list.
 * @param {number} direction - 1 for next, -1 for previous.
 */
function changePage(direction) {
  const totalPages = Math.ceil(allPosts.length / POSTS_PER_PAGE);
  const newPage = currentPage + direction;

  if (newPage >= 1 && newPage <= totalPages) {
    currentPage = newPage;
    renderPosts();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

/**
 * Initializes the application.
 */
async function initializeApp() {
  loadingIndicator.style.display = "block";

  const posts = await loadPostsFromJSON();

  if (posts.length === 0) {
    loadingIndicator.style.display = "none";
    errorMessage.textContent =
      errorMessage.textContent ||
      "Could not load any posts. Run the Python scraper first!";
    errorMessage.style.display = "block";
    return;
  }

  allPosts = posts;

  // --- SORTING LOGIC ---
  // Sort by 'publishDate' in ascending order (Oldest to Newest)
  // Data is already sorted in the JSON file, but we ensure it here too
  allPosts.sort((a, b) => {
    const dateA = new Date(a.publishDate).getTime();
    const dateB = new Date(b.publishDate).getTime();
    return dateA - dateB;
  });
  // --- END SORTING LOGIC ---

  loadingIndicator.style.display = "none";

  // Initial render
  renderPosts();

  // Setup listeners
  prevBtn.addEventListener("click", () => changePage(-1));
  nextBtn.addEventListener("click", () => changePage(1));

  goBtn.addEventListener("click", () => {
    const targetPage = parseInt(pageInput.value);
    const totalPages = Math.ceil(allPosts.length / POSTS_PER_PAGE);

    if (targetPage >= 1 && targetPage <= totalPages) {
      currentPage = targetPage;
      renderPosts();
      window.scrollTo({ top: 0, behavior: "smooth" });
      pageInput.value = "";
    } else {
      alert(`Please enter a page number between 1 and ${totalPages}`);
    }
  });

  pageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      goBtn.click();
    }
  });
}

// Initialize the app on window load
window.onload = initializeApp;
