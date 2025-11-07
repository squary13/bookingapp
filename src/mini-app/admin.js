const API_URL = "https://booking-worker-py-be.squary50.workers.dev";

window.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("status");
  const userList = document.getElementById("userList");

  async function loadUsers() {
    status.textContent = "⏳ Загружаем пользователей...";
    try {
      const res = await fetch(`${API_URL}/api/users`);
      const users = await res.json();
      if (!Array.isArray(users)) {
        status.textContent = `⚠️ ${users.error || "Ошибка загрузки"}`;
        return;
      }
      status.textContent = `✅ Найдено пользователей: ${users.length}`;
      userList.innerHTML = users.map(user => `
        <div class="user-card">
          <strong>${user.name}</strong> (${user.role})<br>
          📱 ${user.phone}<br>
          🆔 ${user.telegram_id}<br>
          🗓️ ${user.created_at}
        </div>
      `).join("");
    } catch (err) {
      status.textContent = "❌ Ошибка соединения с API";
      console.error("Ошибка загрузки пользователей:", err);
    }
  }

  window.generateSlots = async function () {
    status.textContent = "⏳ Генерация слотов...";
    try {
      const res = await fetch(`${API_URL}/api/generate-slots`, { method: "POST" });
      const result = await res.json();
      if (result.ok) {
        status.textContent = `✅ Слоты созданы: ${result.generated}`;
        alert(`Слоты созданы: ${result.generated}`);
      } else {
        status.textContent = `⚠️ Ошибка: ${result.error || "Неизвестно"}`;
        alert(`Ошибка: ${result.error || "Неизвестно"}`);
      }
    } catch (err) {
      status.textContent = "❌ Ошибка генерации";
      alert("Ошибка соединения с API");
    }
  };

  await loadUsers();
});