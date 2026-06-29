(() => {
  const root = document.querySelector("[data-landing]");
  if (!root) {
    return;
  }

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const revealItems = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
    );

    revealItems.forEach((item) => revealObserver.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const target = document.querySelector(anchor.getAttribute("href"));
      if (!target) {
        return;
      }

      event.preventDefault();
      target.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "start",
      });
    });
  });

  const cursor = document.querySelector("[data-cursor]");
  if (cursor && !prefersReducedMotion && window.matchMedia("(pointer: fine)").matches) {
    let cursorX = window.innerWidth / 2;
    let cursorY = window.innerHeight / 2;
    let renderedX = cursorX;
    let renderedY = cursorY;

    window.addEventListener("pointermove", (event) => {
      cursorX = event.clientX;
      cursorY = event.clientY;
    });

    const renderCursor = () => {
      renderedX += (cursorX - renderedX) * 0.12;
      renderedY += (cursorY - renderedY) * 0.12;
      cursor.style.transform = `translate3d(${renderedX}px, ${renderedY}px, 0) translate3d(-50%, -50%, 0)`;
      requestAnimationFrame(renderCursor);
    };

    renderCursor();
  }

  document.querySelectorAll(".magnetic").forEach((button) => {
    if (prefersReducedMotion || !window.matchMedia("(pointer: fine)").matches) {
      return;
    }

    button.addEventListener("pointermove", (event) => {
      const rect = button.getBoundingClientRect();
      const x = event.clientX - rect.left - rect.width / 2;
      const y = event.clientY - rect.top - rect.height / 2;
      button.style.transform = `translate(${x * 0.12}px, ${y * 0.18}px)`;
    });

    button.addEventListener("pointerleave", () => {
      button.style.transform = "";
    });
  });

  document.querySelectorAll("[data-tilt]").forEach((panel) => {
    if (prefersReducedMotion || !window.matchMedia("(pointer: fine)").matches) {
      return;
    }

    panel.addEventListener("pointermove", (event) => {
      const rect = panel.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      panel.style.transform = `perspective(1200px) rotateX(${y * -4}deg) rotateY(${x * 5}deg)`;
    });

    panel.addEventListener("pointerleave", () => {
      panel.style.transform = "";
    });
  });

  const counters = document.querySelectorAll("[data-count]");
  const animateCounter = (counter) => {
    const target = Number(counter.getAttribute("data-count")) || 0;
    const duration = 1350;
    const startTime = performance.now();

    const step = (now) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      counter.textContent = Math.round(target * eased).toLocaleString();

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    };

    requestAnimationFrame(step);
  };

  if ("IntersectionObserver" in window) {
    const counterObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            counterObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );

    counters.forEach((counter) => counterObserver.observe(counter));
  } else {
    counters.forEach(animateCounter);
  }

  const floatingItems = document.querySelectorAll("[data-float]");
  if (floatingItems.length && !prefersReducedMotion) {
    let ticking = false;

    const updateFloatingItems = () => {
      const scrolled = window.scrollY || 0;
      floatingItems.forEach((item, index) => {
        const offset = Math.sin(scrolled * 0.006 + index) * 8;
        item.style.transform = `translate3d(0, ${offset}px, 0)`;
      });
      ticking = false;
    };

    window.addEventListener(
      "scroll",
      () => {
        if (!ticking) {
          window.requestAnimationFrame(updateFloatingItems);
          ticking = true;
        }
      },
      { passive: true }
    );
  }

  const canvas = document.querySelector("[data-particle-field]");
  if (!canvas || prefersReducedMotion) {
    return;
  }

  const context = canvas.getContext("2d", { alpha: true });
  if (!context) {
    return;
  }

  let width = 0;
  let height = 0;
  let dpr = 1;
  let particles = [];
  let pointerX = 0;
  let pointerY = 0;
  let hasPointer = false;

  const palette = [
    "rgba(37, 99, 235, 0.22)",
    "rgba(14, 165, 233, 0.2)",
    "rgba(20, 184, 166, 0.18)",
  ];

  const createParticle = () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.36,
    vy: (Math.random() - 0.5) * 0.36,
    size: Math.random() * 1.8 + 0.7,
    color: palette[Math.floor(Math.random() * palette.length)],
  });

  const resizeCanvas = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);

    const desiredCount = Math.min(54, Math.max(24, Math.floor((width * height) / 26000)));
    particles = Array.from({ length: desiredCount }, createParticle);
  };

  const drawConnections = () => {
    for (let i = 0; i < particles.length; i += 1) {
      for (let j = i + 1; j < particles.length; j += 1) {
        const a = particles[i];
        const b = particles[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance < 124) {
          context.strokeStyle = `rgba(37, 99, 235, ${0.07 * (1 - distance / 124)})`;
          context.lineWidth = 1;
          context.beginPath();
          context.moveTo(a.x, a.y);
          context.lineTo(b.x, b.y);
          context.stroke();
        }
      }
    }
  };

  const updateParticle = (particle) => {
    if (hasPointer) {
      const dx = particle.x - pointerX;
      const dy = particle.y - pointerY;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance < 180 && distance > 0) {
        const force = (180 - distance) / 180;
        particle.vx += (dx / distance) * force * 0.018;
        particle.vy += (dy / distance) * force * 0.018;
      }
    }

    particle.x += particle.vx;
    particle.y += particle.vy;
    particle.vx *= 0.992;
    particle.vy *= 0.992;

    if (particle.x < 0 || particle.x > width) {
      particle.vx *= -1;
    }

    if (particle.y < 0 || particle.y > height) {
      particle.vy *= -1;
    }

    particle.x = Math.max(0, Math.min(width, particle.x));
    particle.y = Math.max(0, Math.min(height, particle.y));
  };

  const renderParticles = () => {
    context.clearRect(0, 0, width, height);
    context.globalCompositeOperation = "lighter";

    particles.forEach((particle) => {
      updateParticle(particle);
      context.beginPath();
      context.fillStyle = particle.color;
      context.shadowBlur = 8;
      context.shadowColor = particle.color;
      context.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
      context.fill();
    });

    context.shadowBlur = 0;
    drawConnections();
    context.globalCompositeOperation = "source-over";
    requestAnimationFrame(renderParticles);
  };

  window.addEventListener("resize", resizeCanvas, { passive: true });
  window.addEventListener(
    "pointermove",
    (event) => {
      pointerX = event.clientX;
      pointerY = event.clientY;
      hasPointer = true;
    },
    { passive: true }
  );
  window.addEventListener("pointerleave", () => {
    hasPointer = false;
  });

  resizeCanvas();
  renderParticles();
})();
