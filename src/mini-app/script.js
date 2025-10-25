const API_URL = "https://booking-worker-py-be.squary50.workers.dev";

window.addEventListener("DOMContentLoaded", async () => {
  const dateInput = document.getElementById("date");
  const timeSelect = document.getElementById("timeSelect");
  const nameInput = document.getElementById("nameInput");
  const phoneInput = document.getElementById("phoneInput");
  const status = document.getElementById("status");
  const records = document.getElementById("records");

  const urlParams = new URLSearchParams(window.location.search);
  const name = urlParams.get("name") || "";
  const userId = parseInt(urlParams.get("user_id"), 10);

  nameInput.value = name;
  document.getElementById("welcomeText").textContent = `👋 Привет, ${name || "Гость"}!`;

  async function fetchAvailableDates() {
    try {
      const res = await fetch(`${API_URL}/api/available-dates`);
      const data = await res.json();
      return data.dates || [];
    } catch {
      return [];
    }
  }

  async function loadSlots(date) {
    timeSelect.innerHTML = "";
    status.textContent = "⏳ Загружаем слоты...";
    try {
      const res = await fetch(`${API_URL}/api/slots?date=${date}`);
      const data = await res.json();
      if (!data.available?.length) {
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
    } catch {
      status.textContent = "❌ Ошибка загрузки слотов";
    }
  }

  async function loadBookings(userId) {
    records.innerHTML = "";
    try {
      const res = await fetch(`${API_URL}/api/bookings?user_id=${userId}`);
      const data = await res.json();
      if (!Array.isArray(data)) {
        records.textContent = `⚠️ ${data.error || "Ошибка загрузки"}`;
        return;
      }
      records.innerHTML = data.length
        ? data.map(r => `📅 ${r.date} в ${r.time}`).join("<br>")
        : "ℹ️ У вас нет записей";
    } catch {
      records.textContent = "❌ Ошибка соединения с API";
    }
  }

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

  document.getElementById("submitBtn").onclick = async () => {
    const payload = {
      user_id: userId,
      date: dateInput.value,
      time: timeSelect.value
    };

    if (!payload.user_id || !payload.date || !payload.time) {
      status.textContent = "⚠️ Все поля обязательны";
      return;
    }

    try {
      const res = await fetch(`${API_URL}/api/bookings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const result = await res.json();
      if (res.status === 201) {
        status.textContent = "✅ Вы успешно записаны!";
        userId ? loadBookings(userId) : loadRecords(name);
      } else {
        status.textContent = `⚠️ ${result.error || "Ошибка записи"}`;
      }
    } catch {
      status.textContent = "❌ Ошибка отправки";
    }
  };

  const availableDates = await fetchAvailableDates();

  flatpickr("#date", {
    dateFormat: "Y-m-d",
    enable: availableDates,
    defaultDate: new Date(),
    onChange: ([selectedDate]) => {
      loadSlots(selectedDate.toISOString().split("T")[0]);
    }
  });

  const today = new Date().toISOString().split("T")[0];
  loadSlots(today);

  if (userId) {
    loadBookings(userId);
  } else if (name) {
    loadRecords(name);
  }
});
