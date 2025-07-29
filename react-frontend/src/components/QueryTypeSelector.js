import React from 'react';
import { Settings, Zap, DollarSign, Code } from 'lucide-react';
import '../QueryTypeSelector.css';

const QueryTypeSelector = ({ queryType, setQueryType }) => {
  const queryTypes = [
    { id: 'general', label: 'General', icon: Settings, description: 'General AWS questions' },
    { id: 'service_recommendation', label: 'Service Recommendation', icon: Zap, description: 'Get AWS service recommendations' },
    { id: 'pricing', label: 'Pricing', icon: DollarSign, description: 'AWS pricing estimates' },
    { id: 'terraform', label: 'Terraform', icon: Code, description: 'Generate Terraform code' }
  ];



  return (
    <div className="query-type-selector">
      <div className="query-types">
        {queryTypes.map(type => {
          const Icon = type.icon;
          return (
            <button
              key={type.id}
              className={`query-type-btn ${queryType === type.id ? 'active' : ''}`}
              onClick={() => setQueryType(type.id)}
              title={type.description}
            >
              <Icon size={16} />
              <span>{type.label}</span>
            </button>
          );
        })}
      </div>
      

    </div>
  );
};

export default QueryTypeSelector;