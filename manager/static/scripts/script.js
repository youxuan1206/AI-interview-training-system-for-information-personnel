const minRequestInterval = 3000;
let lastRequestTime = 0;
let apiKey = ""; // 新增一個變數來存儲 API 金鑰
let url = ""; // 新增一個變數來存儲 API URL

async function submitcontent() {
    let prompt="";
    const currentTime = Date.now();

    if (currentTime - lastRequestTime < minRequestInterval) {
        console.log("Too many requests. Please try again later.");
        return;
    }

    lastRequestTime = currentTime;
    // 從 savedData 中取得最後一個搜尋結果的內容
    const lastSearchResult = savedData[savedData.length - 1];
    const userInput = lastSearchResult ? lastSearchResult.content : ""; // 使用最後一個搜尋結果的內容
    const chatOutput = document.getElementById("chat-output");

    if (!userInput) {
        alert("無法取得題目。");
        return;
    }

    prompt = `我希望你成為一位IT公司的面試官,我會給你一個題目,請你提供與該題目相似的題目並在文字描述上做出差異,且提供的範例也需要與題目的內容做出差異,至少生成三題，題與題之間用~~隔開，並請用你的程式設計原則、語法、資料結構等知識，確保你給的題目是沒有問題的。我的題目是`;
    prompt += '「' + userInput + '」\n';
    url = '../static/data/api_config.json'; // 設定配置檔路徑
    try {
        // 調用函數從配置檔中讀取 API 金鑰和 URL
        await fetchApiConfig();
        const result = await callOpenAPI(prompt);
        const res = analyzeResponse(result);
        addMessageToChat("GPT", res);
    } catch (error) {
        console.error("調用 OpenAI API 時出錯:", error.message);
        addMessageToChat("GPT", "對不起，處理您的請求時出現錯誤。");
    }

    document.getElementById("user-input").value = "";
    chatOutput.scrollTop = chatOutput.scrollHeight;
}

async function fetchApiConfig() {
    const response = await fetch(url);
    const data = await response.json();
    apiKey = data.apiKey; // 從配置檔中讀取 API 金鑰
    url = data.url; // 從配置檔中讀取 API URL
}

async function callOpenAPI(prompt) {
    const payload = {
        model: "gpt-3.5-turbo",
        messages: [{ role: "user", content: prompt }]
    };

    const headers = {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json"
    };

    const response = await fetch(url, {
        method: "POST",
        headers: headers,
        body: JSON.stringify(payload)
    });

    if (response.status === 429) {
        throw new Error("Too many requests. Please try again later.");
    }

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
}

function analyzeResponse(data) {
    const jsonData = data.choices[0].message.content;
    return jsonData;
}

function addMessageToChat(sender, message) {
    const chatOutput = document.getElementById("chat-output");
    const messages = message.split("~~"); // 使用~~作為題目之間的分隔符

    // 清空所有消息內容
    chatOutput.innerHTML = "";

    messages.forEach((msg, index) => {
        // 檢查消息是否為空
        if (msg.trim() !== "") {
            chatOutput.innerHTML += `
                <div class="message">
                    <div class="question" contenteditable="true">${msg}</div>
                    <input type="checkbox" id="checkbox${index}" class="save-checkbox">
                    <label for="checkbox${index}">選擇此題</label>
                </div>`;
        }

        // 添加事件監聽器，以便於當內容被修改時觸發
        document.querySelectorAll('.question').forEach(item => {
            item.addEventListener('input', event => {
                // 在這裡添加你想要的處理程序，比如將修改的內容儲存到某個地方
                console.log('內容已修改:', event.target.innerText);
            });
        });

    });
}
