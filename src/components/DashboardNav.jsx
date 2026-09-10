import { useEffect, useState } from 'react'


const navItems = [
  {
    id: 'monitoring',
    label: 'Monitoring'
  },
  {
    id: 'grafik',
    label: 'Grafik'
  },
  {
    id: 'statistik',
    label: 'Statistik'
  },
  {
    id: 'spasial',
    label: 'Spasial'
  },
  {
    id: 'iot',
    label: 'Kinerja IoT'
  },
  {
    id: 'peta',
    label: 'Peta'
  },
  {
    id: 'ai',
    label: 'AI'
  },
  {
    id: 'riwayat',
    label: 'Riwayat'
  }
]


function DashboardNav() {

  const [activeSection, setActiveSection] =
    useState('monitoring')


  // =========================================
  // SCROLL KE SECTION
  // =========================================

  const goToSection = (sectionId) => {

    const section =
      document.getElementById(sectionId)


    if (!section) {
      return
    }


    section.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    })

  }



  // =========================================
  // DETEKSI SECTION YANG SEDANG AKTIF
  // =========================================

  useEffect(() => {

    const sections =
      navItems
        .map((item) =>
          document.getElementById(item.id)
        )
        .filter(Boolean)


    if (sections.length === 0) {
      return
    }


    const observer =
      new IntersectionObserver(

        (entries) => {

          const visibleEntries =
            entries
              .filter(
                (entry) =>
                  entry.isIntersecting
              )
              .sort(
                (a, b) =>
                  b.intersectionRatio
                  - a.intersectionRatio
              )


          if (visibleEntries.length > 0) {

            setActiveSection(
              visibleEntries[0].target.id
            )

          }

        },

        {
          root: null,
          rootMargin:
            '-100px 0px -55% 0px',

          threshold: [
            0.05,
            0.15,
            0.3,
            0.5
          ]
        }

      )


    sections.forEach(
      (section) =>
        observer.observe(section)
    )


    return () => {

      sections.forEach(
        (section) =>
          observer.unobserve(section)
      )

      observer.disconnect()

    }

  }, [])



  return (

    <div className="sticky top-0 z-[2000] -mx-6 mb-8 border-y border-slate-800 bg-slate-950/95 px-6 py-3 shadow-lg shadow-slate-950/30 backdrop-blur">


      <div className="mx-auto flex max-w-7xl items-center gap-2 overflow-x-auto">


        <div className="mr-2 shrink-0">

          <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">
            Navigasi
          </p>

        </div>


        {
          navItems.map(
            (item) => {

              const isActive =
                activeSection === item.id


              return (

                <button
                  key={item.id}
                  type="button"
                  onClick={() =>
                    goToSection(item.id)
                  }
                  className={`shrink-0 rounded-lg border px-3 py-2 text-xs font-medium transition ${
                    isActive
                      ? 'border-cyan-400/50 bg-cyan-400 text-slate-950 shadow-sm shadow-cyan-400/10'
                      : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-cyan-500/40 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  {item.label}
                </button>

              )

            }
          )
        }


      </div>


    </div>

  )

}


export default DashboardNav
