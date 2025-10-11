const API_URL = "https://bookingapp123.pages.dev";
 // замени на свой

window.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("date");
  const timeSelect = document.getElementById("timeSelect");
  const nameInput = document.getElementById("nameInput");
  const phoneInput = document.getElementById("phoneInput");
  const status = document.getElementById("status");
  const records = document.getElementById("records");

  // Автозаполнение имени из URL
  const urlParams = new URLSearchParams(window.location.search);
  const name = urlParams.get("name") || "";
  nameInput.value = name;
  document.getElementById("welcomeText").textContent = `👋 Привет, ${name || "Гость"}!`;

  // Установка сегодняшней даты
  const today = new Date().toISOString().split("T")[0];
  dateInput.value = today;

  // Загрузка слотов
  async function loadSlots(date) {
    timeSelect.innerHTML = "";
    status.textContent = "⏳ Загружаем слоты...";
    try {
      const res = await fetch(`${API_URL}/api/slots?date=${date}`);
      const data = await res.json();
      if (!data.available.length) {
        status.textContent = "⚠️ Нет доступных слотов";
        return;
      }
      data.available.forEach(slot => {
        const option = document.createElement("option");
        option.value = slot;
        option.textContent = slot;
        timeSelect.appendChild(option);
      });
      status.textContent = "✅ Слоты загружены";
    } catch (err) {
      status.textContent = "❌ Ошибка загрузки слотов";
    }
  }

  // Загрузка записей
  async function loadRecords(name) {
    records.innerHTML = "";
    try {
      const res = await fetch(`${API_URL}/api/myrecord?name=${encodeURIComponent(name)}`);
      const data = await res.json();
      data.records.forEach(rec => {
        const div = document.createElement("div");
        div.textContent = `${rec.date} в ${rec.time}`;
        records.appendChild(div);
      });
    } catch {
      records.textContent = "❌ Ошибка загрузки записей";
    }
  }

  // Отправка записи
  document.getElementById("submitBtn").onclick = async () => {
    const payload = {
      date: dateInput.value,
      time: timeSelect.value,
      name: nameInput.value,
      phone: phoneInput.value
    };
    try {
      const res = await fetch(`${API_URL}/api/book`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const result = await res.json();
      status.textContent = result.success ? "✅ Вы успешно записаны!" : "⚠️ Ошибка записи";
      loadRecords(payload.name);
    } catch {
      status.textContent = "❌ Ошибка отправки";
    }
  };

  // Инициализация
  loadSlots(today);
  if (name) loadRecords(name);

  dateInput.addEventListener("change", () => {
    loadSlots(dateInput.value);
  });
});
