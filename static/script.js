document.getElementById("analyze-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const githubUrl = document.getElementById("github-url").value;
    const explanationsDiv = document.getElementById("explanations");
    const resultsSection = document.getElementById("results");
    const qaSection = document.getElementById("qa-section");
    const loader = document.getElementById("loader");

    // Show loader, hide results and Q&A
    loader.classList.remove("hidden");
    resultsSection.classList.add("hidden");
    qaSection.classList.add("hidden");
    explanationsDiv.innerHTML = "";

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ github_url: githubUrl })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let result = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            result += decoder.decode(value, { stream: true });
            const lines = result.split("\n");
            result = lines.pop(); // Keep incomplete line for next chunk
            for (const line of lines) {
                if (line.trim()) {
                    const data = JSON.parse(line);
                    if (data.status === "success") {
                        explanationsDiv.innerHTML += `<strong>${data.file}</strong>:\n${data.explanation}\n\n`;
                        resultsSection.classList.remove("hidden"); // Show results as they arrive
                    } else if (data.status === "error") {
                        explanationsDiv.innerHTML += `<span class="error">Error: ${data.message}</span>\n`;
                    }
                }
            }
        }

        // Hide loader and show Q&A after completion
        loader.classList.add("hidden");
        qaSection.classList.remove("hidden");
    } catch (error) {
        loader.classList.add("hidden");
        resultsSection.classList.remove("hidden");
        explanationsDiv.innerHTML = `<span class="error">Error: ${error.message}</span>`;
    }
});

document.getElementById("qa-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = document.getElementById("question").value;
    const answerDiv = document.getElementById("answer");

    answerDiv.innerHTML = "Processing your question...";

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ question: question })
        });
        const data = await response.json();

        if (data.status === "success") {
            answerDiv.innerHTML = data.answer;
        } else {
            answerDiv.innerHTML = `<span class="error">Error: ${data.message}</span>`;
        }
    } catch (error) {
        answerDiv.innerHTML = `<span class="error">Error: ${error.message}</span>`;
    }

    document.getElementById("question").value = "";
});