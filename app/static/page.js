
const stickyElm = document.querySelector('.cluster .title')

const observer = new IntersectionObserver( 
  ([e]) => e.target.classList.toggle('isSticky', e.intersectionRatio < 1),
  {threshold: [1]}
);

observer.observe(stickyElm)