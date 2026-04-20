const usernameInput = document.getElementById("username-field");
const passwordInput = document.getElementById("password-field");
const signupForm = document.getElementById("signup-form");

if (usernameInput) {
  const usernamePattern = /^JEC\d{3}$/;

  usernameInput.addEventListener("input", () => {
    const username = usernameInput.value.trim();

    if (!username || usernamePattern.test(username)) {
      usernameInput.setCustomValidity("");
      return;
    }

    usernameInput.setCustomValidity(
      "Username must start with 'JEC' and be followed by 3 numeric characters"
    );
  });
}

if (passwordInput) {
  passwordInput.addEventListener("input", () => {
    const password = passwordInput.value;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasSymbols = /[^\w\s]/.test(password);
    const minCriteria = 3;

    if (
      !password ||
      (password.length >= 8 &&
        [hasUpperCase, hasLowerCase, hasNumbers, hasSymbols].filter((c) => c)
          .length >= minCriteria)
    ) {
      passwordInput.setCustomValidity("");
      return;
    }

    passwordInput.setCustomValidity(
      "Password must be at least 8 characters long and contain at least 3 of the following: uppercase letters, lowercase letters, numbers, symbols"
    );
  });
}

if (signupForm) {
  signupForm.addEventListener("submit", (event) => {
    if (!signupForm.checkValidity()) {
      event.preventDefault();
      signupForm.reportValidity();
    }
  });
}

// // Select the password input field and create a new button element
// const toggleButton = document.createElement("button");

// // Set the text and type of the toggle button
// toggleButton.innerText = "Show";
// toggleButton.type = "button";

// // Add a click event listener to toggle the password visibility
// toggleButton.addEventListener("click", () => {
//   if (passwordInput.type === "password") {
//     passwordInput.type = "text";
//     toggleButton.innerText = "Hide";
//   } else {
//     passwordInput.type = "password";
//     toggleButton.innerText = "Show";
//   }
// });

// // Add the toggle button to the DOM
// passwordInput.parentNode.appendChild(toggleButton);

