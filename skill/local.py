"""Nearby Schools + Nearby Amenities.

Schools are read from the MLS export. Ratings and amenities are researched per
subdivision and stored here, because no MLS export carries them. Update the
PROFILES dict when running a new subdivision.
"""
from core import INK,PINE,SAGE,BRONZE,BRZT,DEEP,SAND,LINE,SOFT,MIST,F,FP

PROFILES={
 'Table Mesa 1': dict(
   district='Boulder Valley School District No. Re2',
   retrieved='July 2026',
   schools=[
     dict(level='Elementary', name='Bear Creek Elementary', grades='K–5',
          gs=10, niche='A', usnews='#7 in Colorado elementary schools',
          enroll=315, ratio='17:1',
          note='Math proficiency 87% vs. 33% statewide; reading 82% vs. 45% statewide. Gifted & Talented program.'),
     dict(level='Middle', name='Southern Hills Middle', grades='6–8',
          gs=9, niche='A', usnews='#12 in Colorado middle schools',
          enroll=493, ratio='20:1',
          note='#8 Best Public Middle School in Colorado (Niche). Math proficiency 65% vs. 33% statewide; reading 83% vs. 45% statewide.'),
     dict(level='High', name='Fairview High', grades='9–12',
          gs=10, niche='A+', usnews='#8 in Colorado · #358 nationally of 17,901 ranked',
          enroll=1847, ratio='22:1',
          note='98% graduation rate vs. 82% statewide. 68% AP participation. SchoolDigger ranks it 6th of 328 Colorado high schools.'),
   ],
   amenities=[
     dict(cat='Shopping', name='Table Mesa Shopping Center',
          detail="South Boulder's main commercial hub with over 50 restaurants, retailers and services, anchored by Whole Foods and including Southern Sun Pub & Brewery and Boxcar Coffee Roasters.",
          why='Everyday retail and dining within walking or short driving distance for the entire subdivision.'),
     dict(cat='Recreation', name='South Boulder Recreation Center',
          detail='City-operated indoor facility with a lap pool with diving board and hot tub, weight and cardio rooms, a gymnasium, dry sauna, and studios for dance, yoga and Pilates.',
          why="The neighborhood's indoor fitness and swim anchor, adjacent to Harlow Platts Park."),
     dict(cat='Park', name='Harlow Platts Community Park & Viele Lake',
          detail='City park with a walking path around Viele Lake (fishing permitted), a nine-hole disc golf course, pickleball and tennis courts, a soccer field, playground and exercise stations.',
          why='The central green space for the subdivision, directly adjacent to Fairview High and Southern Hills Middle.'),
     dict(cat='Trails', name='NCAR trailhead & Mesa Trail',
          detail="City of Boulder Open Space trailhead at the west end of Table Mesa Drive, at the National Center for Atmospheric Research. Connects to the 13.2-mile Mesa Trail and to South Mesa, Shanahan and Bear Canyon trails, with access toward Bear Peak and South Boulder Peak.",
          why='Direct foothills trail access is one of the most-cited draws for buyers in this subdivision.'),
     dict(cat='Institution', name='National Center for Atmospheric Research (NCAR)',
          detail='Federal atmospheric science research campus at the west end of Table Mesa Drive, with public trails and an interpretive nature trail on its grounds.',
          why='A defining neighborhood landmark and open-space buffer at the base of the Flatirons.'),
   ],
   sources='GreatSchools.org, Niche.com, U.S. News & World Report and SchoolDigger (school ratings, retrieved July 2026); City of Boulder Parks & Recreation and Open Space & Mountain Parks, and NCAR (amenities).'
 ),
 'Rossborough': dict(
   district='Poudre School District R-1',
   retrieved='July 2026',
   schools=[
     dict(level='Elementary', name='Johnson Elementary', grades='PK–5',
          gs=9, niche='B+', usnews='#245 in Colorado elementary schools',
          enroll=348, ratio='17:1',
          note='Gifted & Talented program. Math proficiency roughly 47–52% vs. 33% statewide; reading roughly 57–63% vs. 45% statewide.'),
     dict(level='Middle', name='Webber Middle', grades='6–8',
          gs=6, niche='A-', usnews='#86 in Colorado middle schools',
          enroll=724, ratio='18:1',
          note='#5 Best Public Middle School in Larimer County (Niche). Gifted & Talented program. Math proficiency 47% vs. 33% statewide; reading 55% vs. 42% statewide.'),
     dict(level='High', name='Rocky Mountain High', grades='9–12',
          gs=8, niche='A-', usnews='#79 in Colorado',
          enroll=2044, ratio='20:1',
          note='88% graduation rate. AP coursework and Gifted & Talented program offered. #5 Best Public High School in Larimer County (Niche).'),
   ],
   amenities=[
     dict(cat='Park', name='Rossborough Park',
          detail='Sixteen-acre neighborhood park at 1630 Casa Grande Blvd maintained by the City of Fort Collins, with playgrounds, basketball courts, picnic shelters with grills, open field areas, and a seasonal mountain bike course.',
          why="The subdivision's namesake park and its closest green space, immediately walkable for most homes."),
     dict(cat='Recreation', name='Spring Canyon Community Park',
          detail='City of Fort Collins destination park at 2626 W. Horsetooth Rd. with a skate park, pump track, BMX track, disc golf, and the water-feature Inspiration Playground.',
          why='The larger recreation anchor just south of the neighborhood, repeatedly cited in listings as a selling point.'),
     dict(cat='Trails', name='Spring Creek Trail',
          detail="Paved multi-use trail running through west Fort Collins along Spring Creek, connecting Rossborough Park to the city's wider trail network.",
          why='Direct walking and biking access from the neighborhood into the citywide trail system.'),
     dict(cat='Reservoir', name='Horsetooth Reservoir & Horsetooth Mountain Open Space',
          detail='Larimer County reservoir and adjoining open space in the foothills west of Fort Collins, with boating, fishing, and a network of hiking and mountain-biking trails including the popular Horsetooth Rock Trail.',
          why="One of the most-cited draws for buyers in this subdivision, minutes from the neighborhood's west side."),
     dict(cat='University', name='Colorado State University',
          detail='Main CSU campus a short drive east of the neighborhood, with athletics, museums, and public lectures and events open to the community.',
          why='Proximity to CSU is a recurring point in local marketing of the area and a draw for university-affiliated buyers.'),
   ],
   sources='GreatSchools.org, Niche.com, U.S. News & World Report and SchoolDigger (school ratings, retrieved July 2026); City of Fort Collins Parks & Recreation and Larimer County (amenities).'
 ),
 'Lewis Pointe': dict(
   district='Adams 12 Five Star Schools',
   retrieved='July 2026',
   schools=[
     dict(level='Elementary', name='Eagleview Elementary', grades='K–5',
          gs=6, niche='B', usnews='Not ranked — U.S. News does not rank elementary schools',
          enroll=468, ratio='17:1',
          note='Gifted & Talented program. Math proficiency 40% vs. 33% statewide.'),
     dict(level='Middle', name='Rocky Top Middle', grades='6–8',
          gs=7, niche='B+', usnews='#127 in Colorado middle schools',
          enroll=1060, ratio='19:1',
          note='#5 Best Public Middle School in Adams County (Niche). Gifted & Talented, 10 sports.'),
     dict(level='High', name='Horizon High', grades='9–12',
          gs=8, niche='B+', usnews='#76 in Colorado · #2,683 nationally of 17,901 ranked',
          enroll=1981, ratio='20:1',
          note='96% graduation rate vs. 82% statewide. 44% AP participation. Named a U.S. News Best High School five years running.'),
   ],
   amenities=[
     dict(cat='Recreation', name='Trail Winds Park & Recreation Center',
          detail='111-acre park immediately south on Holly Street, with an 87,000 sq ft recreation center: lap pool, leisure pool, lazy river and water slides, climbing wall, elevated indoor track, gymnasium, and a community theater. Outside are ballfields, tennis and basketball courts, a skate park, dog-friendly areas and a playground.',
          why='The single strongest amenity in the area, and the closest.'),
     dict(cat='Golf', name='Todd Creek Golf Club',
          detail='Arthur Hills–designed public championship course opened in 2007, par 72 at up to 7,435 yards with a 74.8 rating and 138 slope. Widely regarded as one of the better public tracks in the north metro, with full dining and event facilities.',
          why='Also in 80602 — a genuine draw for golf buyers.'),
     dict(cat='Trails', name='Signal Ditch & Lee Lateral Trail network',
          detail='A connected paved system running through northern Thornton. The Signal Ditch Trail covers roughly 3.3 miles from 128th Avenue northwest to 141st Drive; the Lee Lateral corridor links east to Eastlake #3 Park & Nature Preserve and Trail Winds Open Space.',
          why='Walkable trail access directly from the neighborhood.'),
     dict(cat='Open space', name='Eastlake Reservoirs & Marshall Lake',
          detail='A quiet 1.5-mile loop circling East Lake #3, popular for birdwatching and water views, plus connections toward Marshall Lake Park and Glen Eagle Open Space.',
          why='Low-key everyday walking close to home.'),
     dict(cat='State park', name='Barr Lake State Park',
          detail='2,715 acres east in Brighton, built around a nearly 2,000-acre reservoir with an 8.8-mile perimeter trail, a gazebo boardwalk, and a nature center. More than 370 bird species recorded; bald eagles winter here and a resident pair nests each year.',
          why='The region’s marquee outdoor destination and a nationally known birding site.'),
     dict(cat='City', name='Thorncreek Golf Course & Margaret Carpenter Park',
          detail='Thornton’s municipal course sits south on Washington Street. Carpenter Park adds a 2.1-mile paved loop around a lake with an amphitheater, boathouse and playgrounds, plus a second city recreation center.',
          why='Rounds out the city’s recreation offering.'),
   ],
   sources='GreatSchools.org, Niche.com and U.S. News & World Report (school ratings, retrieved July 2026); Colorado Parks & Wildlife, City of Thornton Parks & Recreation, and course/facility operators (amenities).'
 ),
}

def scorecard(prof):
    """Each assigned school with its ratings exactly as each publisher reports them.
    The meter shows the GreatSchools 1-10 rating only, which is that publisher's own
    native scale. Niche and U.S. News are shown as text because they are not 1-10
    ratings and are not converted."""
    sch=prof['schools']; W,RH=760,74; H=len(sch)*RH+56
    s=f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="School ratings by source">'
    s+=f'<text x="0" y="12" font-size="9" fill="{SOFT}" letter-spacing="1.5" font-family="{F}">GREATSCHOOLS RATING &#183; 1 TO 10, AS PUBLISHED</text>'
    for i,sc in enumerate(sch):
        y=28+i*RH; g=sc['gs']
        col=PINE if g>=8 else (SAGE if g>=6 else BRONZE)
        tcol=PINE if g>=6 else BRZT
        s+=f'<text x="0" y="{y+14:.0f}" font-size="7.4" fill="{SOFT}" letter-spacing="1.3" font-family="{F}">{sc["level"].upper()} &#183; GRADES {sc["grades"]}</text>'
        s+=f'<text x="0" y="{y+31:.0f}" font-size="12.5" fill="{INK}" font-family="{FP}" font-weight="600">{sc["name"]}</text>'
        s+=f'<text x="0" y="{y+46:.0f}" font-size="8.6" fill="{SOFT}" font-family="{F}">{sc["enroll"]:,} students &#183; {sc["ratio"]} ratio</text>'
        BX=290; SW=26; GP=4
        for k in range(10):
            fill=col if k < g else '#E4EAF2'
            s+=f'<rect x="{BX+k*(SW+GP)}" y="{y+14}" width="{SW}" height="20" rx="2.5" fill="{fill}"/>'
        s+=f'<text x="{BX+10*(SW+GP)+10}" y="{y+30:.0f}" font-size="17" font-weight="700" fill="{tcol}" font-family="{FP}">{g}</text>'
        s+=f'<text x="{BX}" y="{y+46:.0f}" font-size="8.4" fill="{SOFT}" font-family="{F}">Niche {sc["niche"]}</text>'
        if i<len(sch)-1:
            s+=f'<line x1="0" y1="{y+58}" x2="{W}" y2="{y+58}" stroke="{LINE}" stroke-width=".6"/>'
    return s+'</svg>'
