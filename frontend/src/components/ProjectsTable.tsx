import type { Project } from '../types'
import { formatPrice, formatUsdCompact } from '../utils/format'

export function ProjectsTable({ projects }: { projects: Project[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Project</th>
            <th className="num">Price</th>
            <th className="num">Market cap</th>
            <th className="num">FDV</th>
            <th className="num">24h volume</th>
            <th className="num">TVL</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((project, index) => (
            <tr key={project.id}>
              <td className="num muted">{index + 1}</td>
              <td>
                <a className="project" href={project.coingecko_url} target="_blank" rel="noreferrer">
                  {project.image && <img src={project.image} alt="" width={24} height={24} loading="lazy" />}
                  <span className="project-name">{project.name}</span>
                  <span className="muted">{project.symbol}</span>
                </a>
              </td>
              <td className="num">{formatPrice(project.current_price)}</td>
              <td className="num">{formatUsdCompact(project.market_cap)}</td>
              <td className="num">{formatUsdCompact(project.fdv)}</td>
              <td className="num">{formatUsdCompact(project.total_volume)}</td>
              <td className="num">{formatUsdCompact(project.tvl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
