// بستن خودکار پیام‌های اطلاع‌رسانی بعد از چند ثانیه
window.setTimeout(() => {
  document.querySelectorAll('.alert').forEach((element) => {
    const alert = bootstrap.Alert.getOrCreateInstance(element);
    alert.close();
  });
}, 4500);
