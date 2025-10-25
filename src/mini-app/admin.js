const API_URL = "https://booking-worker-py-be.squary50.workers.dev";

async function loadAllUsers() {
  const container = document.getElementById("userList");
  try {
    const res = await fetch(`${API_URL}/api/users`);
    const users = await res.json();
    if (!Array.isArray(users)) {
      container.textContent = "⚠️ Ошибка загрузки";
      return;
    }

    container.innerHTML = users.map(user => `
      <div class="user-card">
        <strong>${user.name}</strong> (${user.phone})<br>
        ID: ${user.telegram_id} | Роль: ${user.role}<br>
        <button onclick="viewBookings(${user.telegram_id})">📅 Записи</button>
        <button onclick="deleteUser(${user.telegram_id})">🗑️ Удалить</button>
      </div>
    `).join("");
  } catch {
    container.textContent = "❌ Ошибка соединения";
  }
}

async function viewBookings(telegram_id) {
  const res = await fetch(`${API_URL}/api/bookings/by-user/${telegram_id}`);
  const bookings = await res.json();
  alert(bookings.length
    ? bookings.map(b => `📅 ${b.date} в ${b.time}`).join("\n")
    : "ℹ️ Нет записей");
}

async function deleteUser(telegram_id) {
  if (!confirm("Удалить пользователя?")) return;
  const res = await fetch(`${API_URL}/api/users/${telegram_id}`, { method: "DELETE" });
  if (res.status === 200) {
    alert("🗑️ Удалено");
    loadAllUsers();
  } else {
    alert("⚠️ Ошибка удаления");
  }
}

window.addEventListener("DOMContentLoaded", loadAllUsers);
