const tg = window.Telegram.WebApp;
tg.expand();

const API_URL = "http://127.0.0.1:8787/api";
const user = tg.initDataUnsafe.user;
document.getElementById("username").innerText = user.first_name;

loadSlots();
loadBookings();

async function loadSlots() {
  const dateInput = document.getElementById("date");
  const timeSelect = document.getElementById("time");

  dateInput.onchange = async () => {
    const date = dateInput.value;
    timeSelect.innerHTML = "";
    try {
      const res = await fetch(`${API_URL}/slots?date=${date}`);
      const data = await res.json();
      data.available.forEach(slot => {
        const option = document.createElement("option");
        option.value = slot;
        option.textContent = slot;
        timeSelect.appendChild(option);
      });
    } catch {
      document.getElementById("status").innerText = "❌ Ошибка загрузки слотов";
    }
  };
}

async function submitBooking() {
  const date = document.getElementById("date").value;
  const time = document.getElementById("time").value;

  if (!date || !time) {
    document.getElementById("status").innerText = "❌ Укажите дату и время";
    return;
  }

  try {
    let res = await fetch(`${API_URL}/users/${user.id}`);
    let userData;
    if (res.status === 200) {
      userData = await res.json();
    } else {
      res = await fetch(`${API_URL}/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          telegram_id: user.id,
          name: user.first_name,
          phone: "0000000",
          role: "user"
        })
      });
      userData = await res.json();
    }

    const booking = {
      user_id: userData.id,
      date,
      time
    };

    res = await fetch(`${API_URL}/bookings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(booking)
    });

    const result = await res.json();
    if (res.status === 201) {
      document.getElementById("status").innerText = "✅ Запись создана!";
      loadBookings();
    } else {
      document.getElementById("status").innerText = `❌ ${result.error}`;
    }
  } catch {
    document.getElementById("status").innerText = "❌ Ошибка сервера";
  }
}

async function loadBookings() {
  const container = document.getElementById("bookings");
  container.innerHTML = "";

  try {
    const resUser = await fetch(`${API_URL}/users/${user.id}`);
    if (resUser.status !== 200) return;

    const userData = await resUser.json();
    const res = await fetch(`${API_URL}/bookings?user_id=${userData.id}`);
    const bookings = await res.json();

    bookings.forEach(b => {
      const div = document.createElement("div");
      div.className = "booking";
      div.innerHTML = `<strong>${b.date} в ${b.time}</strong><br/>`;
      const btn = document.createElement("button");
      btn.textContent = "❌ Удалить";
      btn.onclick = () => deleteBooking(b.id);
      div.appendChild(btn);
      container.appendChild(div);
    });
  } catch {
    container.innerText = "❌ Ошибка загрузки записей";
  }
}

async function deleteBooking(id) {
  try {
    const res = await fetch(`${API_URL}/bookings/${id}`, { method: "DELETE" });
    if (res.status === 200) {
      document.getElementById("status").innerText = "✅ Запись удалена";
      loadBookings();
    } else {
      document.getElementById("status").innerText = "❌ Ошибка удаления";
    }
  } catch {
    document.getElementById("status").innerText = "❌ Ошибка сервера";
  }
}
